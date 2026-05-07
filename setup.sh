#!/bin/bash
set -e
echo "=== Setting up MAIRS v2 ==="

# Pull code
git clone https://github.com/YOUR_USERNAME/mairs-v2 /root/mairs-v2
cd /root/mairs-v2

# Install dependencies
pip install -r requirements.txt

# Configure AWS CLI for Spaces
pip install awscli
aws configure set aws_access_key_id $SPACES_KEY
aws configure set aws_secret_access_key $SPACES_SECRET

# Download model from Spaces (if already trained)
if aws s3 ls s3://mairs-storage/model-final/ --endpoint $SPACES_ENDPOINT 2>/dev/null; then
  echo "Downloading fine-tuned model..."
  aws s3 sync s3://mairs-storage/model-final/ ./fine_tuning/mairs-llama-3.1-8b/ \
    --endpoint $SPACES_ENDPOINT
fi

# Download ChromaDB (if seeded)
if aws s3 ls s3://mairs-storage/chroma_db/ --endpoint $SPACES_ENDPOINT 2>/dev/null; then
  echo "Downloading ChromaDB..."
  aws s3 sync s3://mairs-storage/chroma_db/ ./data/chroma_db/ \
    --endpoint $SPACES_ENDPOINT
fi

echo "=== Setup complete ==="
