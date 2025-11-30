#!/bin/bash
#
# Google Drive Backup Script with Versioning
# ===========================================
# Tự động sync user_data/ lên Google Drive với version control
# Yêu cầu: rclone đã cấu hình với Google Drive
#
# Usage: ./backup_to_drive.sh [full|incremental|models]
#
# Cron setup (backup hàng ngày lúc 2:00 AM):
#   0 2 * * * /path/to/scripts/backup_to_drive.sh incremental >> /path/to/logs/backup.log 2>&1

set -e

# =====================================================
# CONFIGURATION
# =====================================================

# Thư mục gốc của project
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Thư mục cần backup
USER_DATA_DIR="${PROJECT_DIR}/user_data"

# Remote name trong rclone (cần setup trước)
RCLONE_REMOTE="gdrive"

# Thư mục đích trên Google Drive
DRIVE_FOLDER="trading-backup"

# Model versioning settings
MAX_MODEL_VERSIONS=5  # Giữ tối đa 5 versions
VERSION_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Log file
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/backup_$(date +%Y%m%d_%H%M%S).log"

# Exclude patterns (không backup)
EXCLUDE_PATTERNS=(
    "*.tmp"
    "*.log"
    "__pycache__/**"
    ".git/**"
    "tradesv3.sqlite-shm"
    "tradesv3.sqlite-wal"
)

# =====================================================
# FUNCTIONS
# =====================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_requirements() {
    # Kiểm tra rclone đã cài đặt
    if ! command -v rclone &> /dev/null; then
        log "ERROR: rclone chưa được cài đặt. Cài đặt: brew install rclone"
        exit 1
    fi
    
    # Kiểm tra remote đã cấu hình
    if ! rclone listremotes | grep -q "^${RCLONE_REMOTE}:"; then
        log "ERROR: rclone remote '${RCLONE_REMOTE}' chưa được cấu hình."
        log "Chạy: rclone config để setup Google Drive"
        exit 1
    fi
    
    # Tạo log directory nếu chưa có
    mkdir -p "$LOG_DIR"
}

build_exclude_args() {
    local args=""
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        args="$args --exclude '$pattern'"
    done
    echo "$args"
}

backup_full() {
    log "=== BẮT ĐẦU FULL BACKUP ==="
    log "Source: ${USER_DATA_DIR}"
    log "Destination: ${RCLONE_REMOTE}:${DRIVE_FOLDER}"
    
    local exclude_args=$(build_exclude_args)
    
    # Sync toàn bộ user_data
    eval "rclone sync '${USER_DATA_DIR}' '${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data' \
        $exclude_args \
        --progress \
        --stats 30s \
        --stats-one-line \
        --transfers 4 \
        --checkers 8 \
        --fast-list" | tee -a "$LOG_FILE"
    
    # Backup config files từ thư mục gốc
    log "Backing up config files..."
    rclone copy "${PROJECT_DIR}/docker-compose.yml" "${RCLONE_REMOTE}:${DRIVE_FOLDER}/config/" 2>&1 | tee -a "$LOG_FILE"
    rclone copy "${PROJECT_DIR}/Dockerfile" "${RCLONE_REMOTE}:${DRIVE_FOLDER}/config/" 2>&1 | tee -a "$LOG_FILE"
    rclone copy "${PROJECT_DIR}/Makefile" "${RCLONE_REMOTE}:${DRIVE_FOLDER}/config/" 2>&1 | tee -a "$LOG_FILE"
    
    # Backup memory-bank
    log "Backing up memory-bank..."
    rclone sync "${PROJECT_DIR}/memory-bank" "${RCLONE_REMOTE}:${DRIVE_FOLDER}/memory-bank" 2>&1 | tee -a "$LOG_FILE"
    
    log "=== FULL BACKUP HOÀN TẤT ==="
}

backup_incremental() {
    log "=== BẮT ĐẦU INCREMENTAL BACKUP ==="
    log "Source: ${USER_DATA_DIR}"
    log "Destination: ${RCLONE_REMOTE}:${DRIVE_FOLDER}"
    
    local exclude_args=$(build_exclude_args)
    
    # Chỉ copy các file mới/thay đổi
    eval "rclone copy '${USER_DATA_DIR}' '${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data' \
        $exclude_args \
        --update \
        --progress \
        --stats 30s \
        --stats-one-line \
        --transfers 4 \
        --checkers 8 \
        --fast-list" | tee -a "$LOG_FILE"
    
    # Backup memory-bank (luôn sync)
    log "Syncing memory-bank..."
    rclone sync "${PROJECT_DIR}/memory-bank" "${RCLONE_REMOTE}:${DRIVE_FOLDER}/memory-bank" 2>&1 | tee -a "$LOG_FILE"
    
    log "=== INCREMENTAL BACKUP HOÀN TẤT ==="
}

show_drive_usage() {
    log "--- Google Drive Usage ---"
    rclone size "${RCLONE_REMOTE}:${DRIVE_FOLDER}" 2>&1 | tee -a "$LOG_FILE"
}

# =====================================================
# VERSIONED MODEL BACKUP
# =====================================================

create_model_metadata() {
    local version_dir="$1"
    local metadata_file="${version_dir}/metadata.json"
    
    # Đếm số features từ run_params.json nếu có
    local features_count="unknown"
    local model_name="unknown"
    
    if [ -f "${USER_DATA_DIR}/models/freqai-xgboost-v2/run_params.json" ]; then
        model_name=$(jq -r '.model_name // "XGBoostRegressor"' "${USER_DATA_DIR}/models/freqai-xgboost-v2/run_params.json" 2>/dev/null || echo "XGBoostRegressor")
    fi
    
    # Tạo metadata
    cat > "$metadata_file" <<EOF
{
    "version": "${VERSION_TIMESTAMP}",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "model_name": "${model_name}",
    "backup_type": "versioned_model",
    "source_dir": "${USER_DATA_DIR}/models",
    "notes": "Auto-generated by backup_to_drive.sh"
}
EOF
    
    log "Created metadata: ${metadata_file}"
}

backup_models_versioned() {
    log "=== BẮT ĐẦU VERSIONED MODEL BACKUP ==="
    
    local models_dir="${USER_DATA_DIR}/models"
    local version_folder="models_${VERSION_TIMESTAMP}"
    local remote_versions_path="${RCLONE_REMOTE}:${DRIVE_FOLDER}/model_versions"
    local remote_version_path="${remote_versions_path}/${version_folder}"
    
    # Kiểm tra models directory tồn tại và không rỗng
    if [ ! -d "$models_dir" ] || [ -z "$(ls -A "$models_dir" 2>/dev/null)" ]; then
        log "WARNING: Models directory empty or not found. Skipping versioned backup."
        return 0
    fi
    
    # Tạo metadata local
    mkdir -p "/tmp/${version_folder}"
    create_model_metadata "/tmp/${version_folder}"
    
    log "Uploading model version: ${version_folder}"
    log "Destination: ${remote_version_path}"
    
    # Upload models với version
    rclone copy "${models_dir}" "${remote_version_path}/models" \
        --progress \
        --stats 30s \
        --transfers 4 2>&1 | tee -a "$LOG_FILE"
    
    # Upload metadata
    rclone copy "/tmp/${version_folder}/metadata.json" "${remote_version_path}/" 2>&1 | tee -a "$LOG_FILE"
    
    # Cleanup temp
    rm -rf "/tmp/${version_folder}"
    
    # Cleanup old versions (giữ MAX_MODEL_VERSIONS gần nhất)
    cleanup_old_model_versions
    
    log "=== VERSIONED MODEL BACKUP HOÀN TẤT ==="
}

cleanup_old_model_versions() {
    log "Checking old model versions to cleanup..."
    
    local remote_versions_path="${RCLONE_REMOTE}:${DRIVE_FOLDER}/model_versions"
    
    # Lấy danh sách versions, sort theo tên (timestamp)
    local versions=$(rclone lsf "${remote_versions_path}" --dirs-only 2>/dev/null | sort -r)
    local count=0
    
    while IFS= read -r version; do
        count=$((count + 1))
        if [ $count -gt $MAX_MODEL_VERSIONS ]; then
            log "Deleting old version: ${version}"
            rclone purge "${remote_versions_path}/${version}" 2>&1 | tee -a "$LOG_FILE"
        fi
    done <<< "$versions"
    
    log "Kept ${MAX_MODEL_VERSIONS} most recent versions"
}

list_model_versions() {
    log "=== AVAILABLE MODEL VERSIONS ==="
    
    local remote_versions_path="${RCLONE_REMOTE}:${DRIVE_FOLDER}/model_versions"
    
    echo ""
    echo "Version                    | Size"
    echo "---------------------------|---------------"
    
    rclone lsf "${remote_versions_path}" --dirs-only 2>/dev/null | sort -r | while read version; do
        local size=$(rclone size "${remote_versions_path}/${version}" --json 2>/dev/null | jq -r '.bytes' 2>/dev/null || echo "0")
        local size_mb=$((size / 1024 / 1024))
        printf "%-26s | %d MB\n" "$version" "$size_mb"
    done
    
    echo ""
}

# =====================================================
# LIGHTWEIGHT MODELS-ONLY BACKUP (tar.gz)
# =====================================================

backup_models_tar() {
    log "=== BẮT ĐẦU LIGHTWEIGHT MODEL BACKUP (tar.gz) ==="
    
    local models_dir="${USER_DATA_DIR}/models"
    local backup_dir="${PROJECT_DIR}/logs/model_backups"
    local tar_filename="models_${VERSION_TIMESTAMP}.tar.gz"
    local tar_path="${backup_dir}/${tar_filename}"
    local remote_tar_path="${RCLONE_REMOTE}:${DRIVE_FOLDER}/model_archives"
    
    # Tạo backup directory nếu chưa có
    mkdir -p "$backup_dir"
    
    # Kiểm tra models directory
    if [ ! -d "$models_dir" ] || [ -z "$(ls -A "$models_dir" 2>/dev/null)" ]; then
        log "WARNING: Models directory empty or not found. Skipping tar backup."
        return 0
    fi
    
    # Tạo tar.gz
    log "Creating compressed archive: ${tar_filename}"
    tar -czf "$tar_path" -C "${USER_DATA_DIR}" models
    
    local tar_size=$(du -h "$tar_path" | cut -f1)
    log "Archive created: ${tar_path} (${tar_size})"
    
    # Upload to Google Drive
    log "Uploading to Google Drive..."
    rclone copy "$tar_path" "${remote_tar_path}/" \
        --progress 2>&1 | tee -a "$LOG_FILE"
    
    # Cleanup local tar (keep only 3 latest)
    log "Cleaning up local archives..."
    ls -t "${backup_dir}"/models_*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
    
    # Cleanup remote archives (keep MAX_MODEL_VERSIONS)
    cleanup_tar_archives
    
    log "=== LIGHTWEIGHT MODEL BACKUP HOÀN TẤT ==="
    log "Archive: ${remote_tar_path}/${tar_filename}"
}

cleanup_tar_archives() {
    log "Checking old tar archives to cleanup..."
    
    local remote_tar_path="${RCLONE_REMOTE}:${DRIVE_FOLDER}/model_archives"
    
    # Lấy danh sách archives, sort theo tên (timestamp)
    local archives=$(rclone lsf "${remote_tar_path}" 2>/dev/null | grep "\.tar\.gz$" | sort -r)
    local count=0
    
    while IFS= read -r archive; do
        [ -z "$archive" ] && continue
        count=$((count + 1))
        if [ $count -gt $MAX_MODEL_VERSIONS ]; then
            log "Deleting old archive: ${archive}"
            rclone delete "${remote_tar_path}/${archive}" 2>&1 | tee -a "$LOG_FILE"
        fi
    done <<< "$archives"
    
    log "Kept ${MAX_MODEL_VERSIONS} most recent archives"
}

list_tar_archives() {
    log "=== AVAILABLE MODEL ARCHIVES (tar.gz) ==="
    
    local remote_tar_path="${RCLONE_REMOTE}:${DRIVE_FOLDER}/model_archives"
    
    echo ""
    echo "Archive                            | Size"
    echo "-----------------------------------|---------------"
    
    rclone lsf "${remote_tar_path}" --format "sp" 2>/dev/null | sort -r -k2 | while read size name; do
        [ -z "$name" ] && continue
        local size_mb=$((size / 1024 / 1024))
        printf "%-34s | %d MB\n" "$name" "$size_mb"
    done
    
    echo ""
}

# =====================================================
# MAIN
# =====================================================

main() {
    log "============================================="
    log "  Google Drive Backup Script (with Versioning)"
    log "============================================="
    
    check_requirements
    
    local mode="${1:-incremental}"
    
    case "$mode" in
        full)
            backup_full
            backup_models_versioned  # Also create versioned backup
            ;;
        incremental)
            backup_incremental
            ;;
        models)
            backup_models_versioned
            ;;
        models-tar)
            backup_models_tar  # Lightweight tar.gz backup
            ;;
        list-versions)
            list_model_versions
            list_tar_archives
            exit 0
            ;;
        *)
            echo "Usage: $0 [full|incremental|models|models-tar|list-versions]"
            echo ""
            echo "Options:"
            echo "  full          - Full sync + create versioned model backup"
            echo "  incremental   - Incremental backup (new/changed files only)"
            echo "  models        - Create versioned model backup (full directory)"
            echo "  models-tar    - Create lightweight model backup (tar.gz, smaller)"
            echo "  list-versions - List available model versions/archives on Drive"
            exit 1
            ;;
    esac
    
    show_drive_usage
    
    log "Backup hoàn tất!"
    log "Log file: ${LOG_FILE}"
}

main "$@"
