#!/bin/bash
# =============================================================================
# Create FreqAI Training VM (Spot Instance)
# For backtesting and FreqAI model training
# Cost: ~$0.30/hr (SPOT - n2-standard-64)
# =============================================================================

set -e

# Config
PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0733808683}"
ZONE="${GCP_ZONE:-us-central1-a}"
SERVICE_ACCOUNT="979257626630-compute@developer.gserviceaccount.com"
VM_NAME="${1:-freqai-train}"
MACHINE_TYPE="${2:-n2-standard-64}"

echo "============================================================"
echo "  🚀 Creating FreqAI Training VM"
echo "============================================================"
echo "  Name: $VM_NAME"
echo "  Machine: $MACHINE_TYPE (64 vCPU, 256GB RAM)"
echo "  Type: SPOT (~70% cheaper!)"
echo "  Disk: 100GB SSD"
echo "  OS: Debian 12"
echo "============================================================"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Create VM
gcloud compute instances create $VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --no-restart-on-failure \
    --maintenance-policy=TERMINATE \
    --provisioning-model=SPOT \
    --instance-termination-action=STOP \
    --service-account=$SERVICE_ACCOUNT \
    --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append \
    --tags=http-server,https-server \
    --create-disk=auto-delete=yes,boot=yes,device-name=$VM_NAME,image=projects/debian-cloud/global/images/debian-12-bookworm-v20251111,mode=rw,size=100,type=pd-ssd \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --reservation-affinity=none \
    --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose git
systemctl enable docker
systemctl start docker
usermod -aG docker $(logname)
echo "Docker installed successfully!" > /var/log/startup-complete.txt
'

echo ""
echo "⏳ Waiting for VM startup script to complete..."
sleep 30

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "============================================================"
echo "  ✅ Training VM Created!"
echo "============================================================"
echo "  Name: $VM_NAME"
echo "  IP: $EXTERNAL_IP"
echo "  Cost: ~$0.30/hr (SPOT)"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. SSH vào VM:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "2. Clone repo & chạy training:"
echo "   git clone YOUR_REPO && cd trading && make train"
echo ""
echo "3. XÓA VM khi xong (quan trọng!):"
echo "   ./scripts/gcp/teardown.sh $VM_NAME"
echo "============================================================"
