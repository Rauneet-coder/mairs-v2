# Fine-Tuning the SRE Incident Response Model

This guide describes how to train the **SRE Incident Response Model** (`Qwen/Qwen2.5-7B-Instruct` using PEFT LoRA) for your multi-agent SRE backend.

Fine-tuning a 7B parameter model requires significant GPU VRAM (~14GB+ to load the model, and 24GB to 48GB+ to train). Local macOS machines lack the necessary GPU hardware. You have two excellent options to train:

---

## 🚀 Option A: Serverless Fine-Tuning via Fireworks AI (Highly Recommended)
*Use your $50 Fireworks AI platform credits! Fully serverless, takes 5 minutes to submit, and costs ~$1.50.*

### 1. Set Your API Key
Get an API Key from the [Fireworks AI Dashboard](https://fireworks.ai/dashboard/api-keys) and export it in your terminal:
```bash
export FIREWORKS_API_KEY="your_fireworks_api_key_here"
```

### 2. Run the Automation Script
Inside the `mairs-v2` directory, run the custom python script:
```bash
python3 fine_tuning/train_fireworks.py
```
This script will automatically:
1. Install the `fireworks-ai` package if not present.
2. Upload your prepared training dataset splits (`train.jsonl` and `val.jsonl`).
3. Submit a Supervised Fine-Tuning (SFT) job to Fireworks using `Qwen2.5-7B-Instruct` as the base model.

### 3. Track and Monitor
You can monitor the live loss charts, evaluation metrics, and completion status on the web dashboard:
👉 **[Fireworks AI Fine-Tuning Dashboard](https://fireworks.ai/dashboard/fine-tuning)**

Once completed, the model will be deployed serverlessly. You can query it like a standard model by passing your model ID to the Fireworks endpoint!

---

## 🛠️ Option B: Self-Managed Fine-Tuning via DigitalOcean GPU Droplet
*For running the raw training script (`train.py`) on dedicated rented hardware.*

### 1. Provision the GPU Droplet on DigitalOcean
1. Sign in to your **DigitalOcean Control Panel**.
2. Click **Create** -> **Droplets**.
3. Under **Choose an image**, select the **Marketplace** tab and search for:
   * **PyTorch** or **TensorFlow/CUDA** (Ubuntu with pre-installed NVIDIA CUDA Drivers and PyTorch is highly recommended as it saves hours of driver setups).
4. Under **Choose size**, select **GPU Droplets**:
   * An **NVIDIA A10G** (24GB VRAM) is perfect and highly cost-effective for this run.
5. Add your **SSH Key** and launch. Copy the Droplet's Public IP (`<DROPLET_IP>`).

### 2. Package and Transfer the Dataset & Training Script
Run these commands on your **local macOS terminal** inside the `mairs-v2/` directory:
```bash
cd /Users/rauneetsingh/Developer/MAIRS/mairs-v2
tar --exclude='venv' --exclude='.git' -czvf fine_tuning.tar.gz fine_tuning/
scp fine_tuning.tar.gz root@<DROPLET_IP>:/root/
```

### 3. Connect and Set Up the Droplet Environment
```bash
# SSH into the remote Droplet
ssh root@<DROPLET_IP>

# Extract the archive
cd /root
tar -xzvf fine_tuning.tar.gz
cd fine_tuning

# Install training libraries (PyTorch is already pre-installed on ML image)
pip install --upgrade pip
pip install transformers peft trl datasets accelerate sentencepiece
```

### 4. Run Training in a Persistent tmux Session
Since fine-tuning takes time, run it in `tmux` to survive SSH disconnects:
```bash
# Start a new tmux session
tmux new -s mairs-training

# Start training
python3 train.py
```
* **How to Detach**: Press `Ctrl + B`, then press `D`.
* **How to Re-attach**: `tmux attach -t mairs-training`

### 5. Download the Fine-Tuned Weights
Once training completes, exit your SSH session and download the LoRA adapter weights locally:
```bash
scp -r root@<DROPLET_IP>:/root/fine_tuning/mairs-llama-3.1-8b /Users/rauneetsingh/Developer/MAIRS/mairs-v2/fine_tuning/
```
*⚠️ **Remember**: Destroy your DigitalOcean Droplet immediately after download to stop hourly charges!*
