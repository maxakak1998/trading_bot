#!/bin/bash
# =============================================================================
# Deploy to GCP VM
# Uploads project files and starts trading bot
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-freqtrade-trading}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="${1:-freqtrade-live}"
LOCAL_PATH="$(dirname "$0")/../.."

echo "🚀 Deploying to VM: $VM_NAME"
echo ""

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo "❌ VM $VM_NAME does not exist"
    echo "   Create it first with: ./scripts/gcp/create-live-vm.sh"
    exit 1
fi

# Create remote directory
echo "📁 Preparing remote directory..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo mkdir -p /opt/freqtrade && sudo chown \$(whoami) /opt/freqtrade"

# Upload configuration files
echo "📤 Uploading configuration files..."
gcloud compute scp $LOCAL_PATH/docker-compose.yml $VM_NAME:/opt/freqtrade/ --zone=$ZONE
gcloud compute scp $LOCAL_PATH/Dockerfile $VM_NAME:/opt/freqtrade/ --zone=$ZONE

# Upload user_data (strategies, configs, models)
echo "📤 Uploading user_data..."
gcloud compute scp --recurse $LOCAL_PATH/user_data/strategies $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE
gcloud compute scp --recurse $LOCAL_PATH/user_data/configs $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE
gcloud compute scp $LOCAL_PATH/user_data/config.json $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE

# Upload models (if exists)
if [ -d "$LOCAL_PATH/user_data/models" ]; then
    echo "📤 Uploading trained models..."
    gcloud compute scp --recurse $LOCAL_PATH/user_data/models $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE
fi

# Upload data (for continuation)
if [ -d "$LOCAL_PATH/user_data/data" ]; then
    echo "📤 Uploading historical data..."
    gcloud compute scp --recurse $LOCAL_PATH/user_data/data $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE
fi

# Start the bot
echo "🤖 Starting FreqTrade bot..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/freqtrade && docker compose pull && docker compose up -d"

# Wait and check status
sleep 5
echo ""
echo "📊 Checking bot status..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/freqtrade && docker compose logs --tail=20"

# Get API endpoint
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Access Information:"
echo "   SSH: gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "   API: http://$EXTERNAL_IP:8080/api/v1/ping"
echo "   Logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/freqtrade && docker compose logs -f'"
echo ""
echo "🔧 Management Commands:"
echo "   Stop:    gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/freqtrade && docker compose down'"
echo "   Restart: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/freqtrade && docker compose restart'"
echo "   Status:  gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/freqtrade && docker compose ps'"
