#!/bin/bash
# =============================================================================
# Create Production VM (e2-small)
# For live trading - minimal cost (~$0.02/hr = ~$15/month)
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0733808683}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="freqtrade-live"
MACHINE_TYPE="e2-small"  # 2 vCPUs, 2GB RAM

echo "🚀 Creating Production VM: $VM_NAME"
echo "   Machine: $MACHINE_TYPE (2 vCPUs, 2GB RAM)"
echo "   Cost: ~$15/month"
echo ""

# Create VM (standard, not spot - need reliability for live trading)
gcloud compute instances create $VM_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --tags=freqtrade-server \
    --metadata=startup-script='#!/bin/bash
# Install Docker
apt-get update
apt-get install -y docker.io docker-compose git
systemctl start docker
systemctl enable docker
usermod -aG docker $USER

# Pull FreqTrade image
docker pull freqtradeorg/freqtrade:develop_freqai

# Create working directory
mkdir -p /opt/freqtrade
cd /opt/freqtrade

# Setup auto-restart on boot
cat > /etc/systemd/system/freqtrade.service << EOF
[Unit]
Description=FreqTrade Trading Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/freqtrade
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
EOF

systemctl enable freqtrade

echo "✅ Production VM setup complete!"
'

echo ""
echo "⏳ Waiting for VM to be ready..."
sleep 30

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Reserve static IP for production
echo "📍 Reserving static IP..."
gcloud compute addresses create freqtrade-live-ip --region=${ZONE%-*} 2>/dev/null || true
STATIC_IP=$(gcloud compute addresses describe freqtrade-live-ip --region=${ZONE%-*} --format='get(address)' 2>/dev/null || echo "N/A")

echo ""
echo "✅ Production VM created successfully!"
echo ""
echo "📋 VM Details:"
echo "   Name: $VM_NAME"
echo "   External IP: $EXTERNAL_IP"
echo "   Static IP: $STATIC_IP"
echo "   Machine: $MACHINE_TYPE"
echo "   Cost: ~$15/month"
echo ""
echo "🔐 Connect with:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "📤 Deploy best model:"
echo "   ./scripts/gcp/deploy.sh"
echo ""
echo "🌐 API Access:"
echo "   http://$EXTERNAL_IP:8080/api/v1/ping"
