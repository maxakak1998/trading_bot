#!/bin/bash
# =============================================================================
# One-Click GCP Trading Bot Pipeline
# Creates VM, clones repo, uploads config, and runs training via Makefile
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0733808683}"
ZONE="${GCP_ZONE:-asia-southeast1-b}"
VM_NAME="${VM_NAME:-trading-bot}"
MACHINE_TYPE="${GCP_MACHINE_TYPE:-n2-standard-32}"
REPO_URL="https://github.com/maxakak1998/trading_bot.git"

# Training parameters (passed to Makefile)
TRAIN_TIMERANGE="${TRAIN_TIMERANGE:-20240101-20240401}"
HYPEROPT_EPOCHS="${HYPEROPT_EPOCHS:-500}"
HYPEROPT_SPACES="${HYPEROPT_SPACES:-buy sell roi}"

echo "🚀 GCP Trading Bot Pipeline"
echo "==========================================="
echo "   VM: $VM_NAME ($MACHINE_TYPE)"
echo "   Zone: $ZONE"
echo "   Train: $TRAIN_TIMERANGE"
echo "   Epochs: $HYPEROPT_EPOCHS"
echo "==========================================="
echo ""

# =============================================================================
# Step 1: Ensure local code is committed
# =============================================================================
echo "📋 Step 1/5: Checking git status..."
cd "$(dirname "$0")/../.."

# Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "⚠️  WARNING: You have uncommitted changes!"
    git status -s
    echo ""
    read -p "Do you want to commit and push now? (y/n): " commit_choice
    if [[ "$commit_choice" == "y" ]]; then
        read -p "Enter commit message: " commit_msg
        git add -A
        git commit -m "$commit_msg"
        git push origin main
        echo "✅ Changes committed and pushed"
    else
        echo "❌ Aborting. Please commit your changes first."
        exit 1
    fi
else
    echo "✅ No uncommitted changes"
fi

# =============================================================================
# Step 2: Create VM with Docker
# =============================================================================
echo ""
echo "📦 Step 2/5: Creating VM..."

# Check if VM exists
if gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo "⚠️  VM $VM_NAME already exists"
    read -p "Delete and recreate? (y/n): " recreate
    if [[ "$recreate" == "y" ]]; then
        gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet
        echo "   Deleted existing VM"
    else
        echo "   Using existing VM"
    fi
fi

# Create VM if not exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    gcloud compute instances create $VM_NAME \
        --project=$PROJECT_ID \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
        --no-restart-on-failure \
        --maintenance-policy=TERMINATE \
        --provisioning-model=SPOT \
        --instance-termination-action=STOP \
        --tags=http-server,https-server \
        --create-disk=auto-delete=yes,boot=yes,device-name=$VM_NAME,image=projects/debian-cloud/global/images/debian-12-bookworm-v20251111,mode=rw,size=100,type=pd-ssd \
        --no-shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring

    echo "⏳ Waiting for VM to be ready..."
    sleep 30

    # Install Docker
    echo "🐳 Installing Docker..."
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="
        sudo apt-get update -qq
        sudo apt-get install -y docker.io docker-compose git make -qq
        sudo systemctl start docker
        sudo usermod -aG docker \$USER
    "
fi

echo "✅ VM ready"

# =============================================================================
# Step 3: Clone repository
# =============================================================================
echo ""
echo "📥 Step 3/5: Cloning repository..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    sudo rm -rf /opt/freqtrade
    sudo mkdir -p /opt/freqtrade
    sudo chown \$USER:\$USER /opt/freqtrade
    git clone $REPO_URL /opt/freqtrade
    cd /opt/freqtrade && ls -la
"
echo "✅ Repository cloned"

# =============================================================================
# Step 4: Upload config files (gitignored)
# =============================================================================
echo ""
echo "📤 Step 4/5: Uploading config files..."

# Upload config.json
if [[ -f "user_data/config.json" ]]; then
    gcloud compute scp user_data/config.json $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE
    echo "   ✅ config.json uploaded"
fi

# Upload env.json (if exists)
if [[ -f "user_data/env.json" ]]; then
    gcloud compute scp user_data/env.json $VM_NAME:/opt/freqtrade/user_data/ --zone=$ZONE
    echo "   ✅ env.json uploaded"
fi

# Upload .env (if exists)
if [[ -f ".env" ]]; then
    gcloud compute scp .env $VM_NAME:/opt/freqtrade/ --zone=$ZONE
    echo "   ✅ .env uploaded"
fi

echo "✅ Config files uploaded"

# =============================================================================
# Step 5: Run Makefile commands
# =============================================================================
echo ""
echo "🎯 Step 5/5: Running training via Makefile..."

# Pull Docker image and start training
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/freqtrade
    
    # Pull Docker image
    sudo docker pull freqtradeorg/freqtrade:develop_freqai
    
    # Create directories
    mkdir -p user_data/models
    
    # Run make train (background)
    echo 'Starting training...'
    nohup make train TRAIN_TIMERANGE=$TRAIN_TIMERANGE > train.log 2>&1 &
    
    echo 'Training started in background'
    sleep 5
    tail -20 train.log
"

# Get VM IP
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "==========================================="
echo "✅ Pipeline Complete!"
echo "==========================================="
echo ""
echo "📋 VM Details:"
echo "   Name: $VM_NAME"
echo "   IP: $EXTERNAL_IP"
echo "   Zone: $ZONE"
echo ""
echo "📊 Monitor training:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE --command='tail -f /opt/freqtrade/train.log'"
echo ""
echo "🎯 Run hyperopt after training:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/freqtrade && make hyperopt HYPEROPT_EPOCHS=$HYPEROPT_EPOCHS HYPEROPT_SPACES=\"$HYPEROPT_SPACES\" TRAIN_TIMERANGE=$TRAIN_TIMERANGE'"
echo ""
echo "📥 Download results:"
echo "   gcloud compute scp $VM_NAME:/opt/freqtrade/user_data/strategies/FreqAIStrategy.json . --zone=$ZONE"
echo ""
echo "⚠️  Delete VM when done:"
echo "   gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet"
