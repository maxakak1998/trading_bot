#!/bin/bash
# =============================================================================
# Model Tournament Script
# Creates 3 parallel VMs to test XGBoost, LightGBM, CatBoost simultaneously
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-freqtrade-trading}"
ZONE="${GCP_ZONE:-us-central1-a}"
MACHINE_TYPE="c2-standard-16"  # 16 vCPUs, 64GB RAM per VM

echo "🏆 Starting Model Tournament"
echo "   Creating 3 VMs for parallel model testing..."
echo ""

MODELS=("xgboost" "lightgbm" "catboost")
FREQAI_MODELS=("XGBoostRegressor" "LightGBMRegressor" "CatBoostRegressor")

for i in ${!MODELS[@]}; do
    MODEL=${MODELS[$i]}
    FREQAI_MODEL=${FREQAI_MODELS[$i]}
    VM_NAME="freqtrade-${MODEL}"
    
    echo "🚀 Creating VM: $VM_NAME for $FREQAI_MODEL"
    
    gcloud compute instances create $VM_NAME \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --provisioning-model=SPOT \
        --instance-termination-action=STOP \
        --boot-disk-size=50GB \
        --boot-disk-type=pd-ssd \
        --image-family=debian-11 \
        --image-project=debian-cloud \
        --tags=freqtrade-server \
        --metadata=startup-script="#!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose
systemctl start docker
systemctl enable docker
docker pull freqtradeorg/freqtrade:develop_freqai
mkdir -p /opt/freqtrade
echo 'VM ready for $FREQAI_MODEL training'
" &
    
done

# Wait for all VMs to be created
wait

echo ""
echo "⏳ Waiting for VMs to initialize..."
sleep 60

echo ""
echo "✅ All tournament VMs created!"
echo ""
echo "📋 VM Summary:"
for MODEL in ${MODELS[@]}; do
    VM_NAME="freqtrade-${MODEL}"
    IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || echo "pending")
    echo "   $VM_NAME: $IP"
done

echo ""
echo "📤 Upload data to all VMs:"
echo "   ./scripts/gcp/upload-to-tournament.sh"
echo ""
echo "🎯 Start tournament:"
echo "   ./scripts/gcp/run-tournament.sh"
echo ""
echo "💰 Estimated cost: ~$0.60/hr for all 3 VMs (Spot)"
