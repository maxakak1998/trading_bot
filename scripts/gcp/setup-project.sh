#!/bin/bash
# =============================================================================
# GCP Project Setup Script
# Sets up Google Cloud project for FreqTrade optimization
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0733808683}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"

echo "🚀 Setting up GCP Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Zone: $ZONE"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install google-cloud-sdk
    else
        echo "Please install gcloud CLI manually: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
fi

# Login if not already authenticated
echo "🔐 Checking authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo "   Logging in to Google Cloud..."
    gcloud auth login
fi

# Create project (may fail if exists)
echo "📁 Creating project: $PROJECT_ID"
gcloud projects create $PROJECT_ID --name="FreqTrade Trading Bot" 2>/dev/null || echo "   Project already exists or name taken"

# Set project
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
gcloud config set compute/zone $ZONE

# Enable billing (user must do this manually via console)
echo ""
echo "⚠️  IMPORTANT: Enable billing for project $PROJECT_ID"
echo "   1. Go to: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
echo "   2. Link your billing account with $300 credit"
echo ""
read -p "Press Enter after enabling billing..."

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com

# Create firewall rules
echo "🔥 Creating firewall rules..."
gcloud compute firewall-rules create allow-freqtrade-api \
    --allow tcp:8080 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow FreqTrade API access" \
    --target-tags freqtrade-server 2>/dev/null || echo "   Firewall rule already exists"

gcloud compute firewall-rules create allow-ssh \
    --allow tcp:22 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow SSH access" 2>/dev/null || echo "   SSH rule already exists"

# Create storage bucket for backups
BUCKET_NAME="${PROJECT_ID}-backups"
echo "🪣 Creating storage bucket: $BUCKET_NAME"
gsutil mb -l $REGION gs://$BUCKET_NAME 2>/dev/null || echo "   Bucket already exists"

# Set budget alerts
echo ""
echo "💰 Setting up budget alerts..."
echo "   Please set up budget alerts manually:"
echo "   1. Go to: https://console.cloud.google.com/billing/budgets"
echo "   2. Create alerts at: $50, $100, $200, $280"
echo ""

# =====================================================
# GOOGLE DRIVE BACKUP SETUP
# =====================================================
echo ""
echo "============================================================"
echo "  📁 GOOGLE DRIVE BACKUP SETUP"
echo "============================================================"
echo ""
echo "FreqTrade sử dụng Google Drive để backup models sau mỗi lần train."
echo ""
read -p "Bạn muốn setup Google Drive backup? [Y/n] " setup_gdrive

if [[ ! "$setup_gdrive" =~ ^[Nn] ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [ -f "${SCRIPT_DIR}/../setup_gdrive.sh" ]; then
        bash "${SCRIPT_DIR}/../setup_gdrive.sh"
    else
        echo "⚠️  setup_gdrive.sh not found at ${SCRIPT_DIR}/../setup_gdrive.sh"
        echo "   Bạn có thể chạy thủ công: ./scripts/setup_gdrive.sh"
    fi
else
    echo "Bỏ qua Google Drive setup."
    echo "Chạy sau: ./scripts/setup_gdrive.sh"
fi

echo ""
echo "============================================================"
echo "  🎉 SETUP HOÀN TẤT!"
echo "============================================================"
echo ""
echo "📋 Project Details:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Zone: $ZONE"
echo "   Backup Bucket: gs://$BUCKET_NAME"
echo ""
echo "🎯 Next steps:"
echo ""
echo "   1. Tạo VM training:"
echo "      ./scripts/gcp/create-train-vm.sh"
echo ""
echo "   2. Hoặc chạy hyperopt:"
echo "      ./scripts/gcp/create-hyperopt-vm.sh"
echo ""
echo "   3. Backup thủ công:"
echo "      ./scripts/backup_to_drive.sh full"
echo ""
echo "   4. XÓA VM khi xong (quan trọng!):"
echo "      ./scripts/gcp/teardown.sh"
echo "============================================================"
