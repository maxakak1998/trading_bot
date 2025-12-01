#!/bin/bash
# =============================================================================
# Create Hyperopt VM (Spot Instance - c2-standard-60)
# For massive hyperopt optimization (5000+ epochs)
# Cost: ~$0.75/hr (Spot) vs ~$2.5/hr (Standard)
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-freqtrade-trading}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="freqtrade-hyperopt"
MACHINE_TYPE="c2-standard-60"  # 60 vCPUs, 240GB RAM

echo "🚀 Creating Hyperopt VM: $VM_NAME"
echo "   Machine: $MACHINE_TYPE (60 vCPUs, 240GB RAM)"
echo "   Type: Spot (Preemptible) - ~$0.75/hr"
echo ""

# Create VM with Spot pricing
gcloud compute instances create $VM_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --provisioning-model=SPOT \
    --instance-termination-action=STOP \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-ssd \
    --image-family=debian-11 \
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
echo "   Machine: $MACHINE_TYPE"
echo "   Cost: ~$0.75/hr (Spot)"
echo ""
echo "🔐 Connect with:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "📤 Upload project files:"
echo "   gcloud compute scp --recurse user_data $VM_NAME:/opt/freqtrade/ --zone=$ZONE"
echo "   gcloud compute scp docker-compose.yml $VM_NAME:/opt/freqtrade/ --zone=$ZONE"
echo ""
echo "🎯 Run hyperopt:"
echo "   cd /opt/freqtrade"
echo "   docker run --rm -v \$(pwd)/user_data:/freqtrade/user_data \\"
echo "     freqtradeorg/freqtrade:develop_freqai hyperopt \\"
echo "     --strategy FreqAIStrategy \\"
echo "     --hyperopt-loss SharpeHyperOptLossDaily \\"
echo "     --spaces buy sell roi stoploss \\"
echo "     --epochs 5000 \\"
echo "     -j 60"
echo ""
echo "⚠️  Remember to delete VM after use to save costs!"
echo "   gcloud compute instances delete $VM_NAME --zone=$ZONE"
