#!/bin/bash
set -e
echo "=== Saving work ==="

# Push code
git add -A && git commit -m "session: $(date +%Y%m%d-%H%M)" && git push

# Upload ChromaDB to Spaces
aws s3 sync ./data/chroma_db s3://mairs-storage/chroma_db/ \
  --endpoint https://blr1.digitaloceanspaces.com

# Upload model if it exists
if [ -d "./fine_tuning/mairs-llama-3.1-8b" ]; then
  aws s3 sync ./fine_tuning/mairs-llama-3.1-8b s3://mairs-storage/model-final/ \
    --endpoint https://blr1.digitaloceanspaces.com
fi

echo "=== Destroying droplet ==="
DROPLET_ID=$(doctl compute droplet list --format ID --no-header | head -1)
if [ -n "$DROPLET_ID" ]; then
  doctl compute droplet delete $DROPLET_ID --force
  echo "Droplet $DROPLET_ID destroyed. Billing stopped."
else
  echo "No droplet found."
fi
