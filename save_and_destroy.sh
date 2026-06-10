#!/bin/bash
set -e
echo "=== Saving work ==="

# Stage any changes
if git diff --cached --quiet && git diff --quiet; then
    echo "No local changes to commit."
else
    git add -A && git commit -m "session: $(date +%Y%m%d-%H%M)" && git push
fi

# Upload ChromaDB to Spaces
aws s3 sync ./data/chroma_db s3://mairs-storage/chroma_db/ \
  --endpoint ${SPACES_ENDPOINT:-https://blr1.digitaloceanspaces.com}

# Upload model if it exists
if [ -d "./fine_tuning/mairs-llama-3.1-8b" ]; then
  aws s3 sync ./fine_tuning/mairs-llama-3.1-8b s3://mairs-storage/model-final/ \
    --endpoint ${SPACES_ENDPOINT:-https://blr1.digitaloceanspaces.com}
fi

echo "=== Destroying droplet ==="
# WARNING: This script targets the droplet by the current hostname.
# If you run multiple droplets, set DROPLET_NAME explicitly before calling.
DROPLET_NAME=${DROPLET_NAME:-"mairs-training"}
DROPLET_ID=$(doctl compute droplet list --format ID,Name --no-header | grep "${DROPLET_NAME}" | awk '{print $1}' | head -1)
if [ -n "$DROPLET_ID" ]; then
  doctl compute droplet delete $DROPLET_ID --force
  echo "Droplet $DROPLET_ID ($DROPLET_NAME) destroyed. Billing stopped."
else
  echo "No droplet found with name '$DROPLET_NAME'."
fi
