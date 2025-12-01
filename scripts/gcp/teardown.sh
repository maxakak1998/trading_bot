#!/bin/bash
# =============================================================================
# Teardown GCP Resources
# Deletes all VMs and resources to stop charges
# =============================================================================

set -e

PROJECT_ID="${GCP_PROJECT_ID:-freqtrade-trading}"
ZONE="${GCP_ZONE:-us-central1-a}"

echo "🗑️  GCP Resource Teardown"
echo "   Project: $PROJECT_ID"
echo ""

# List all VMs
echo "📋 Current VMs:"
gcloud compute instances list --format="table(name,zone,machineType,status)"

echo ""
read -p "⚠️  Delete all freqtrade VMs? (y/N): " CONFIRM

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Cancelled."
    exit 0
fi

# Delete VMs
VMS=$(gcloud compute instances list --filter="name~freqtrade" --format="value(name)")

for VM in $VMS; do
    echo "🗑️  Deleting VM: $VM"
    gcloud compute instances delete $VM --zone=$ZONE --quiet &
done

wait
echo ""
echo "✅ All VMs deleted!"

# Ask about other resources
echo ""
read -p "🪣 Delete storage bucket (backups will be lost)? (y/N): " DELETE_BUCKET

if [[ "$DELETE_BUCKET" == "y" || "$DELETE_BUCKET" == "Y" ]]; then
    BUCKET_NAME="${PROJECT_ID}-backups"
    echo "🗑️  Deleting bucket: $BUCKET_NAME"
    gsutil rm -r gs://$BUCKET_NAME 2>/dev/null || echo "   Bucket not found or already deleted"
fi

# Show remaining resources
echo ""
echo "📋 Remaining resources:"
gcloud compute instances list
gcloud compute addresses list

echo ""
echo "✅ Teardown complete!"
echo ""
echo "💰 Check billing to confirm no charges:"
echo "   https://console.cloud.google.com/billing"
