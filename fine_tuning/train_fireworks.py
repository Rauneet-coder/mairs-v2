#!/usr/bin/env python3
"""Fine-tune Qwen 2.5 7B Instruct on Fireworks AI using your API credits."""

import os
import sys
from pathlib import Path

try:
    from fireworks.client import Fireworks
except ImportError:
    print("📦 Installing required Fireworks AI Python SDK...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "fireworks-ai"])
    from fireworks.client import Fireworks

def main():
    api_key = os.environ.get("FIREWORKS_API_KEY")
    if not api_key:
        print("❌ Error: FIREWORKS_API_KEY environment variable is not set.")
        print("\nPlease export it in your terminal before running this script:")
        print("   export FIREWORKS_API_KEY=\"your_api_key_here\"")
        print("\nYou can get your API Key from: https://fireworks.ai/dashboard/api-keys")
        sys.exit(1)

    root = Path(__file__).resolve().parents[1]
    dataset_dir = root / "fine_tuning" / "dataset"
    train_path = dataset_dir / "train.jsonl"
    val_path = dataset_dir / "val.jsonl"

    if not train_path.exists() or not val_path.exists():
        print(f"❌ Error: Dataset splits not found at {train_path} or {val_path}.")
        print("Please run `python3 -m fine_tuning.prepare_dataset` first.")
        sys.exit(1)

    print("🔌 Connecting to Fireworks AI...")
    client = Fireworks(api_key=api_key)

    # Fireworks dataset IDs must be lowercase and contain only alphanumeric and hyphens.
    train_dataset_id = "mairs-sre-train-dataset"
    val_dataset_id = "mairs-sre-val-dataset"

    print(f"📤 Uploading training dataset from {train_path}...")
    try:
        client.datasets.upload(
            dataset_id=train_dataset_id,
            file=train_path
        )
        print(f"✅ Training dataset uploaded successfully as: {train_dataset_id}")
    except Exception as e:
        print(f"⚠️ Dataset upload status (it might already exist): {e}")

    print(f"📤 Uploading validation dataset from {val_path}...")
    try:
        client.datasets.upload(
            dataset_id=val_dataset_id,
            file=val_path
        )
        print(f"✅ Validation dataset uploaded successfully as: {val_dataset_id}")
    except Exception as e:
        print(f"⚠️ Dataset upload status (it might already exist): {e}")

    base_model = "accounts/fireworks/models/qwen2p5-7b-instruct"
    display_name = "mairs-sre-qwen-7b"
    output_model_id = "mairs-sre-qwen-7b-lora"

    print(f"\n🚀 Launching SFT Fine-Tuning job using base model '{base_model}'...")
    try:
        job = client.create_supervised_fine_tuning_job(
            base_model=base_model,
            dataset=train_dataset_id,
            display_name=display_name,
            output_model=output_model_id,
            epochs=3,
            learning_rate=2e-4,
        )
        print("\n🎉 Success! Fine-tuning job successfully submitted to Fireworks AI.")
        print(f"Job ID: {job.id}")
        print("You can monitor and track its loss charts at:")
        print(f"👉 https://fireworks.ai/dashboard/fine-tuning")
        print("\nOnce training completes, your fine-tuned model will be instantly deployable")
        print(f"as a serverless endpoint under your Fireworks account!")
    except Exception as e:
        print(f"❌ Failed to submit job via SDK: {e}")
        print("\nAlternative (CLI method):")
        print("If you prefer using the command-line, run the official CLI commands:")
        print(f"  1. Upload: firectl dataset create {train_dataset_id} {train_path}")
        print(f"  2. Upload: firectl dataset create {val_dataset_id} {val_path}")
        print(f"  3. Launch: firectl sftj create --base-model {base_model} --dataset {train_dataset_id} --output-model {output_model_id} --epochs 3")

if __name__ == "__main__":
    main()
