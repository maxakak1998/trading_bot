#!/bin/bash
#
# Google Drive Restore Script
# ===========================
# Khôi phục user_data/ từ Google Drive
# Yêu cầu: rclone đã cấu hình với Google Drive
#
# Usage: ./restore_from_drive.sh [all|data|models|strategies|config]
#
# WARNING: Script này sẽ GHI ĐÈ dữ liệu local!

set -e

# =====================================================
# CONFIGURATION
# =====================================================

# Thư mục gốc của project
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Thư mục cần restore
USER_DATA_DIR="${PROJECT_DIR}/user_data"

# Remote name trong rclone
RCLONE_REMOTE="gdrive"

# Thư mục nguồn trên Google Drive
DRIVE_FOLDER="trading-backup"

# Log file
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/restore_$(date +%Y%m%d_%H%M%S).log"

# Backup local trước khi restore
BACKUP_BEFORE_RESTORE=true

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
    
    # Kiểm tra backup tồn tại trên Drive
    if ! rclone lsd "${RCLONE_REMOTE}:${DRIVE_FOLDER}" &> /dev/null; then
        log "ERROR: Không tìm thấy backup tại ${RCLONE_REMOTE}:${DRIVE_FOLDER}"
        exit 1
    fi
    
    # Tạo log directory nếu chưa có
    mkdir -p "$LOG_DIR"
}

confirm_action() {
    local message="$1"
    read -p "$message [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

backup_local() {
    if [ "$BACKUP_BEFORE_RESTORE" = true ]; then
        local backup_dir="${USER_DATA_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
        log "Backup local data trước khi restore..."
        log "Backup to: ${backup_dir}"
        cp -r "$USER_DATA_DIR" "$backup_dir" 2>/dev/null || true
    fi
}

restore_all() {
    log "=== RESTORE TẤT CẢ DỮ LIỆU ==="
    
    backup_local
    
    # Restore user_data
    log "Restoring user_data..."
    rclone sync "${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data" "${USER_DATA_DIR}" \
        --progress \
        --stats 30s \
        --transfers 4 | tee -a "$LOG_FILE"
    
    # Restore memory-bank
    log "Restoring memory-bank..."
    rclone sync "${RCLONE_REMOTE}:${DRIVE_FOLDER}/memory-bank" "${PROJECT_DIR}/memory-bank" \
        --progress | tee -a "$LOG_FILE"
    
    # Restore config files
    log "Restoring config files..."
    rclone copy "${RCLONE_REMOTE}:${DRIVE_FOLDER}/config/" "${PROJECT_DIR}/" \
        --progress | tee -a "$LOG_FILE"
    
    log "=== RESTORE HOÀN TẤT ==="
}

restore_data() {
    log "=== RESTORE DATA (OHLCV) ==="
    
    rclone sync "${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data/data" "${USER_DATA_DIR}/data" \
        --progress \
        --stats 30s \
        --transfers 4 | tee -a "$LOG_FILE"
    
    log "=== RESTORE DATA HOÀN TẤT ==="
}

restore_models() {
    log "=== RESTORE MODELS ==="
    
    rclone sync "${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data/models" "${USER_DATA_DIR}/models" \
        --progress \
        --transfers 4 | tee -a "$LOG_FILE"
    
    rclone sync "${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data/freqaimodels" "${USER_DATA_DIR}/freqaimodels" \
        --progress | tee -a "$LOG_FILE"
    
    log "=== RESTORE MODELS HOÀN TẤT ==="
}

restore_strategies() {
    log "=== RESTORE STRATEGIES ==="
    
    rclone sync "${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data/strategies" "${USER_DATA_DIR}/strategies" \
        --progress | tee -a "$LOG_FILE"
    
    log "=== RESTORE STRATEGIES HOÀN TẤT ==="
}

restore_config() {
    log "=== RESTORE CONFIG ==="
    
    # Restore config.json
    rclone copy "${RCLONE_REMOTE}:${DRIVE_FOLDER}/user_data/config.json" "${USER_DATA_DIR}/" \
        --progress | tee -a "$LOG_FILE"
    
    # Restore root config files
    rclone copy "${RCLONE_REMOTE}:${DRIVE_FOLDER}/config/" "${PROJECT_DIR}/" \
        --progress | tee -a "$LOG_FILE"
    
    log "=== RESTORE CONFIG HOÀN TẤT ==="
}

list_available_backups() {
    log "--- Danh sách backup trên Google Drive ---"
    rclone lsd "${RCLONE_REMOTE}:${DRIVE_FOLDER}" 2>&1 | tee -a "$LOG_FILE"
    echo ""
    log "--- Kích thước backup ---"
    rclone size "${RCLONE_REMOTE}:${DRIVE_FOLDER}" 2>&1 | tee -a "$LOG_FILE"
}

show_usage() {
    echo "Usage: $0 [all|data|models|strategies|config|list]"
    echo ""
    echo "Options:"
    echo "  all        - Restore tất cả dữ liệu (WARNING: ghi đè local)"
    echo "  data       - Restore chỉ OHLCV data"
    echo "  models     - Restore chỉ AI models"
    echo "  strategies - Restore chỉ strategies code"
    echo "  config     - Restore chỉ config files"
    echo "  list       - Liệt kê backups có sẵn trên Drive"
    echo ""
    echo "Examples:"
    echo "  $0 models     # Restore models từ Drive"
    echo "  $0 all        # Restore toàn bộ"
}

# =====================================================
# MAIN
# =====================================================

main() {
    log "============================================="
    log "  Google Drive Restore Script"
    log "============================================="
    
    check_requirements
    
    local target="${1:-help}"
    
    case "$target" in
        all)
            if confirm_action "WARNING: Sẽ ghi đè TẤT CẢ dữ liệu local. Tiếp tục?"; then
                restore_all
            else
                log "Đã hủy restore."
                exit 0
            fi
            ;;
        data)
            restore_data
            ;;
        models)
            restore_models
            ;;
        strategies)
            restore_strategies
            ;;
        config)
            restore_config
            ;;
        list)
            list_available_backups
            ;;
        help|--help|-h)
            show_usage
            exit 0
            ;;
        *)
            log "ERROR: Unknown option: $target"
            show_usage
            exit 1
            ;;
    esac
    
    log "Restore hoàn tất!"
    log "Log file: ${LOG_FILE}"
}

main "$@"
