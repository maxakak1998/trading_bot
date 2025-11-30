#!/bin/bash
#
# rclone Google Drive Setup Script
# =================================
# Hướng dẫn và tự động setup rclone với Google Drive API
#
# Prerequisites:
# - Google Drive API đã enabled trong Google Cloud Console
# - Có OAuth credentials (Client ID và Client Secret)
#
# Usage: ./setup_gdrive.sh

set -e

# =====================================================
# CONFIGURATION
# =====================================================

REMOTE_NAME="gdrive"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# =====================================================
# FUNCTIONS
# =====================================================

print_header() {
    echo ""
    echo "============================================="
    echo "  rclone Google Drive Setup"
    echo "============================================="
    echo ""
}

check_rclone() {
    if ! command -v rclone &> /dev/null; then
        echo "rclone chưa được cài đặt."
        echo ""
        echo "Cài đặt trên macOS:"
        echo "  brew install rclone"
        echo ""
        echo "Hoặc download từ: https://rclone.org/downloads/"
        exit 1
    fi
    echo "✓ rclone đã cài đặt: $(rclone version | head -1)"
}

check_existing_remote() {
    if rclone listremotes | grep -q "^${REMOTE_NAME}:"; then
        echo ""
        echo "⚠️  Remote '${REMOTE_NAME}' đã tồn tại!"
        echo ""
        read -p "Bạn muốn xóa và tạo lại? [y/N] " response
        if [[ "$response" =~ ^[Yy] ]]; then
            rclone config delete "${REMOTE_NAME}"
            echo "✓ Đã xóa remote cũ"
        else
            echo "Giữ nguyên remote hiện tại."
            test_connection
            exit 0
        fi
    fi
}

show_instructions() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  HƯỚNG DẪN SETUP GOOGLE DRIVE API"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Bạn cần chuẩn bị 2 thông tin từ Google Cloud Console:"
    echo ""
    echo "1. CLIENT ID     - từ OAuth 2.0 Client IDs"
    echo "2. CLIENT SECRET - từ OAuth 2.0 Client IDs"
    echo ""
    echo "Nếu chưa có, làm theo các bước:"
    echo ""
    echo "Step 1: Truy cập Google Cloud Console"
    echo "   → https://console.cloud.google.com/apis/credentials"
    echo ""
    echo "Step 2: Tạo OAuth 2.0 Client ID"
    echo "   → Create Credentials → OAuth client ID"
    echo "   → Application type: Desktop app"
    echo "   → Name: rclone"
    echo ""
    echo "Step 3: Download credentials và lấy Client ID + Secret"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

setup_rclone() {
    echo "Bắt đầu cấu hình rclone..."
    echo ""
    
    # Nhập Client ID
    read -p "Nhập Google OAuth Client ID: " client_id
    if [ -z "$client_id" ]; then
        echo "ERROR: Client ID không được để trống"
        exit 1
    fi
    
    # Nhập Client Secret
    read -p "Nhập Google OAuth Client Secret: " client_secret
    if [ -z "$client_secret" ]; then
        echo "ERROR: Client Secret không được để trống"
        exit 1
    fi
    
    echo ""
    echo "Đang tạo rclone config..."
    echo ""
    
    # Tạo config tự động với interactive auth
    cat << EOF | rclone config create "${REMOTE_NAME}" drive \
        client_id "${client_id}" \
        client_secret "${client_secret}" \
        scope "drive" \
        root_folder_id "" \
        service_account_file ""
EOF

    echo ""
    echo "rclone sẽ mở browser để authorize..."
    echo "Vui lòng đăng nhập Google và cho phép quyền truy cập."
    echo ""
    
    # Chạy auth
    rclone config reconnect "${REMOTE_NAME}:"
}

test_connection() {
    echo ""
    echo "Testing kết nối Google Drive..."
    echo ""
    
    if rclone lsd "${REMOTE_NAME}:" &> /dev/null; then
        echo "✓ Kết nối Google Drive thành công!"
        echo ""
        echo "Các thư mục trong Drive:"
        rclone lsd "${REMOTE_NAME}:" | head -10
        
        # Kiểm tra/tạo thư mục backup
        echo ""
        echo "Kiểm tra thư mục backup..."
        if ! rclone lsd "${REMOTE_NAME}:trading-backup" &> /dev/null; then
            echo "Tạo thư mục trading-backup trên Drive..."
            rclone mkdir "${REMOTE_NAME}:trading-backup"
            rclone mkdir "${REMOTE_NAME}:trading-backup/user_data"
            rclone mkdir "${REMOTE_NAME}:trading-backup/config"
            rclone mkdir "${REMOTE_NAME}:trading-backup/memory-bank"
            echo "✓ Đã tạo cấu trúc thư mục backup"
        else
            echo "✓ Thư mục trading-backup đã tồn tại"
        fi
    else
        echo "✗ Không thể kết nối Google Drive"
        echo "Kiểm tra lại credentials hoặc chạy: rclone config"
        exit 1
    fi
}

show_next_steps() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  SETUP HOÀN TẤT!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Bây giờ bạn có thể sử dụng:"
    echo ""
    echo "  # Backup lên Google Drive"
    echo "  ./scripts/backup_to_drive.sh full"
    echo ""
    echo "  # Restore từ Google Drive"
    echo "  ./scripts/restore_from_drive.sh list"
    echo ""
    echo "  # Setup cron job backup hàng ngày (2:00 AM)"
    echo "  crontab -e"
    echo "  # Thêm dòng:"
    echo "  0 2 * * * ${PROJECT_DIR}/scripts/backup_to_drive.sh incremental"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# =====================================================
# MAIN
# =====================================================

main() {
    print_header
    check_rclone
    check_existing_remote
    show_instructions
    
    read -p "Bạn đã có Client ID và Client Secret? [y/N] " response
    if [[ ! "$response" =~ ^[Yy] ]]; then
        echo ""
        echo "Vui lòng tạo OAuth credentials trước."
        echo "Truy cập: https://console.cloud.google.com/apis/credentials"
        exit 0
    fi
    
    setup_rclone
    test_connection
    show_next_steps
}

main "$@"
