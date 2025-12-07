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
# Calculate JOBS from machine type (n2-standard-32 → 28 jobs, leave 4 CPUs for system)
VCPUS=$(echo $MACHINE_TYPE | grep -oE '[0-9]+$' || echo "8")
JOBS="${JOBS:-$((VCPUS > 4 ? VCPUS - 4 : VCPUS))}"

echo "🚀 GCP Trading Bot Pipeline"
echo "==========================================="
echo "   VM: $VM_NAME ($MACHINE_TYPE)"
echo "   Zone: $ZONE"
echo "   Train: $TRAIN_TIMERANGE"
echo "   Epochs: $HYPEROPT_EPOCHS"
echo "   Jobs: $JOBS"
echo "==========================================="
echo ""

# =============================================================================
# Step 1: Ensure local code is committed
# =============================================================================
echo "📋 Step 1/5: Checking git status..."
cd "$(dirname "$0")/../.."

# Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "⚠️  Uncommitted changes detected. Auto-committing..."
    git add -A
    git commit -m "auto: GCP pipeline commit $(date +%Y%m%d_%H%M%S)"
    git push origin main
    echo "✅ Changes auto-committed and pushed"
else
    echo "✅ No uncommitted changes"
fi

# =============================================================================
# Step 2: Create VM with Docker
# =============================================================================
echo ""
echo "📦 Step 2/5: Creating VM..."

# Check if VM exists - use existing if available
if gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo "✅ VM $VM_NAME already exists, using existing VM"
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

    # Install Docker and build custom image
    echo "🐳 Installing Docker and building custom image..."
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="
        sudo apt-get update -qq
        sudo apt-get install -y docker.io docker-compose git make -qq
        sudo systemctl start docker
        sudo usermod -aG docker \$USER
        
        # Pull base image
        sudo docker pull freqtradeorg/freqtrade:develop_freqai
        
        # Create Dockerfile with datasieve fix
        cat > /tmp/Dockerfile << 'DOCKERFILE'
FROM freqtradeorg/freqtrade:develop_freqai

# Fix datasieve version for ftuser
USER ftuser
RUN pip uninstall -y datasieve && pip install datasieve==0.1.9
DOCKERFILE
        
        # Build custom image
        cd /tmp && sudo docker build -t freqtrade-custom:latest .
        echo '✅ Custom Docker image built'
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

# Start training with custom image
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/freqtrade
    
    # Create directories
    mkdir -p user_data/models
    
    # Run make train with custom image (background)
    echo 'Starting training with custom Docker image...'
    nohup make train TRAIN_TIMERANGE=$TRAIN_TIMERANGE DOCKER_IMAGE=freqtrade-custom:latest > train.log 2>&1 &
    
    echo 'Training started in background'
    sleep 10
    tail -30 train.log || echo 'Waiting for log...'
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
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/freqtrade && make hyperopt HYPEROPT_EPOCHS=$HYPEROPT_EPOCHS HYPEROPT_SPACES=\"$HYPEROPT_SPACES\" TRAIN_TIMERANGE=$TRAIN_TIMERANGE JOBS=$JOBS DOCKER_IMAGE=freqtrade-custom:latest'"
echo ""
echo "📥 Download results:"
echo "   gcloud compute scp $VM_NAME:/opt/freqtrade/user_data/strategies/FreqAIStrategy.json . --zone=$ZONE"
echo ""
echo "⚠️  Delete VM when done:"
echo "   gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet"
