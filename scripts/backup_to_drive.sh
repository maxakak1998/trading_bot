#!/bin/bash
#
# Google Drive Backup Script
# ==========================
# Tự động sync user_data/ lên Google Drive
# Yêu cầu: rclone đã cấu hình với Google Drive
#
# Usage: ./backup_to_drive.sh [full|incremental]
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
# MAIN
# =====================================================

main() {
    log "============================================="
    log "  Google Drive Backup Script"
    log "============================================="
    
    check_requirements
    
    local mode="${1:-incremental}"
    
    case "$mode" in
        full)
            backup_full
            ;;
        incremental)
            backup_incremental
            ;;
        *)
            log "Usage: $0 [full|incremental]"
            exit 1
            ;;
    esac
    
    show_drive_usage
    
    log "Backup hoàn tất!"
    log "Log file: ${LOG_FILE}"
}

main "$@"
