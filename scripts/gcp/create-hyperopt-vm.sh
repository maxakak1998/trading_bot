#!/bin/bash
# =============================================================================
# Create Hyperopt VM (Spot Instance - n2-standard-128)
# For massive hyperopt optimization (5000+ epochs)
# Cost: ~$0.60/hr (Spot)
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0733808683}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="trading-bot"
MACHINE_TYPE="n2-standard-32"  # 32 vCPUs, 128GB RAM - fits quota limit
SERVICE_ACCOUNT="979257626630-compute@developer.gserviceaccount.com"

echo "🚀 Creating Hyperopt VM: $VM_NAME"
echo "   Machine: $MACHINE_TYPE (128 vCPUs, 512GB RAM)"
echo "   Type: Spot (Preemptible) - ~$0.60/hr"
echo ""

# Create VM with Spot pricing - matching user's exact config
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
    --labels=goog-ec-src=vm_add-gcloud \
    --reservation-affinity=none \
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

echo "✅ VM setup complete! Ready for hyperopt."
'

echo ""
echo "⏳ Waiting for VM to be ready..."
sleep 30

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "✅ Hyperopt VM created successfully!"
echo ""
echo "📋 VM Details:"
echo "   Name: $VM_NAME"
echo "   IP: $EXTERNAL_IP"
echo "   Machine: $MACHINE_TYPE (128 vCPUs)"
echo "   Cost: ~$0.60/hr (Spot)"
echo ""
echo "🔐 Connect with:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "📤 Upload project files:"
echo "   gcloud compute scp --recurse user_data $VM_NAME:/opt/freqtrade/ --zone=$ZONE"
echo "   gcloud compute scp docker-compose.yml $VM_NAME:/opt/freqtrade/ --zone=$ZONE"
echo ""
echo "🎯 Run hyperopt with 128 CPUs:"
echo "   cd /opt/freqtrade"
echo "   docker run --rm -v \$(pwd)/user_data:/freqtrade/user_data \\"
echo "     freqtradeorg/freqtrade:develop_freqai hyperopt \\"
echo "     --strategy FreqAIStrategy \\"
echo "     --hyperopt-loss SharpeHyperOptLossDaily \\"
echo "     --spaces buy sell roi \\"
echo "     --epochs 5000 \\"
echo "     --timerange 20230101-20240401 \\"
echo "     -j 100"
echo ""
echo "⚠️  Remember to delete VM after use to save costs!"
echo "   gcloud compute instances delete $VM_NAME --zone=$ZONE"
