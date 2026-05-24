# Custom LLM Fine-Tuning on DigitalOcean (Bare-Metal & OS Images)

This guide provides a comprehensive, step-by-step blueprint for provisioning, configuring, and executing fine-tuning jobs for Large Language Models (specifically **Qwen 2.5 7B** using PEFT LoRA) on **DigitalOcean**. 

It covers two deployment strategies:
1. **Automated ML/GPU Droplets** (using pre-configured marketplace images to save hours).
2. **Vanilla Custom OS Images** (building the environment entirely from scratch on a clean OS, using manual NVIDIA/CUDA installations, and saving/reusing standard Snapshots).

---

## 🏗️ Section 1: DigitalOcean Provisioning Strategies

To fine-tune a 7B-parameter model like Qwen2.5, you will need a GPU with at least **24GB of VRAM** (e.g., an **NVIDIA A10G**) to support LoRA/QLoRA training configurations with batch size 4 and a sequence length of 2048.

### Option A: Pre-Configured Marketplace Images (Fastest)
DigitalOcean offers high-performance GPU Droplets with pre-installed machine learning stacks (NVIDIA Drivers, CUDA Toolkit, PyTorch, etc.).
1. Log in to the **DigitalOcean Control Panel**.
2. Click **Create** ➔ **Droplets**.
3. Under **Choose an image**, click the **Marketplace** tab and search for:
   * **PyTorch** or **CUDA** on Ubuntu.
4. Under **Choose Size**, toggle **GPU Droplets** and select:
   * **NVIDIA A10G (24GB VRAM)** or an **NVIDIA A100 (80GB VRAM)** for faster throughput.
5. Assign your **SSH Keys**, choose your region (e.g., NYC1 or SFO3), and click **Create Droplet**.

---

### Option B: Custom OS Images & Snapshots (Full Control)
If you require custom Linux kernels, specialized security hardening, or want to create a reusable machine image (like an AMI in AWS), you can build and register a custom OS image.

#### 1. Importing a Custom OS Image
If you have an existing VM image configured locally (VirtualBox, QEMU, Vagrant):
1. Export the VM to one of the supported formats: `.qcow2`, `.vmdk`, `.vdi`, `.vhd`, or `.raw`.
2. Compress the image (e.g., `gzip custom-ubuntu-22.04.qcow2`).
3. In the DigitalOcean panel, go to **Images** ➔ **Custom Images**.
4. Click **Upload Image**, choose your file, select the distribution (e.g., **Ubuntu**), and select your target datacenter.
5. Once uploaded, you can select this image when launching your next GPU Droplet.

#### 2. Creating a Reusable Machine Snapshot
Instead of installing drivers and packages every time you rent a GPU:
1. Spin up a standard **Ubuntu 22.04 LTS** Droplet.
2. Complete **Section 2 (NVIDIA & CUDA Driver Setup)** below.
3. Power down the droplet:
   ```bash
   shutdown -h now
   ```
4. In the DigitalOcean Panel, go to the Droplet's **Snapshots** tab, enter a name (e.g., `cuda-12.4-pytorch-base`), and click **Take Snapshot**.
5. You can now spin up new GPU Droplets instantly using this snapshot under **Images** ➔ **Snapshots**.

---

## 🛠️ Section 2: Low-Level OS & Driver Configuration (From Scratch)

If you chose a **Vanilla Custom OS Image** or a clean standard **Ubuntu 22.04 LTS** image, you must configure the GPU drivers and CUDA compiler from scratch.

> [!WARNING]
> Do NOT install NVIDIA drivers using standard `apt install nvidia-driver`. This often links outdated repository versions, resulting in CUDA mismatch issues. Always use the official CUDA Network Repositories.

### 1. Update OS & Install Core Utilities
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y build-essential cmake curl git wget tmux htop ca-certificates python3-pip python3-venv
```

### 2. Install NVIDIA Proprietary Drivers & CUDA Toolkit (CUDA 12.4)
Execute the following to register the official NVIDIA Ubuntu 22.04 packages and install the CUDA stack:

```bash
# Pin and download CUDA keyring
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb

# Update apt repositories
sudo apt-get update

# Install CUDA Toolkit and NVIDIA Drivers
sudo apt-get -y install cuda-toolkit-12-4 nvidia-driver-550-open
```

### 3. Configure Shell Environment Variables
Add CUDA binaries to your `PATH` and system libraries to `LD_LIBRARY_PATH`:
```bash
echo 'export PATH=/usr/local/cuda-12.4/bin${PATH:+:${PATH}}' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> ~/.bashrc
source ~/.bashrc
```

### 4. Reboot the Server
A system reboot is required to load the new kernel-level NVIDIA GPU modules:
```bash
sudo reboot
```

### 5. Verify the Installation
After logging back in via SSH, verify the kernel modules and compilers are operational:
```bash
# Verify GPU connectivity and VRAM
nvidia-smi

# Verify CUDA Compiler version
nvcc --version
```
*Expected output:* `nvidia-smi` should output details of your active GPU (e.g., NVIDIA A10G) and `nvcc` should output `Cuda compilation tools, release 12.4`.

---

## 🐍 Section 3: Setting Up the ML Environment

Once the CUDA layers are operational, initialize the python isolation layer and compile deep-learning requirements.

### 1. Initialize Virtual Environment
```bash
cd /root
python3 -m venv ml-env
source ml-env/bin/activate
pip install --upgrade pip
```

### 2. Install PyTorch with Native CUDA Support
Check compatibility with your CUDA driver (CUDA 12.4 uses the `cu124` PyTorch wheel):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 3. Install ML Fine-Tuning Libraries
```bash
pip install transformers peft trl datasets accelerate sentencepiece bitsandbytes
```

### 4. Verify GPU Access in Python
```python
python3 -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device Name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```
*Expected output:* `CUDA Available: True` and `Device Name: NVIDIA A10G` (or similar active GPU).

---

## 📂 Section 4: Transferring Code and Datasets

Before execution, bundle your local project files (the fine-tuning scripts and datasets) and transfer them directly to the DigitalOcean Droplet.

### 1. Package Project Locally (macOS Terminal)
Run these commands from your local computer inside the `mairs-v2` directory:
```bash
cd /Users/rauneetsingh/Developer/MAIRS/mairs-v2

# Archive only the fine_tuning files (excluding logs and virtual environments)
tar --exclude='venv' --exclude='.git' --exclude='__pycache__' -czvf fine_tuning.tar.gz fine_tuning/

# Securely copy to your DigitalOcean droplet IP
scp fine_tuning.tar.gz root@<DROPLET_IP>:/root/
```

### 2. Extract Archive on Droplet (SSH Terminal)
On your remote DigitalOcean droplet:
```bash
cd /root
tar -xzvf fine_tuning.tar.gz
cd fine_tuning
```

---

## 🚀 Section 5: Executing the Fine-Tuning Job

### 1. Launch a Persistent Terminal Session
LLM training takes hours. Connection drops will abort the script if run in a standard terminal. Use `tmux` to ensure persistent execution:
```bash
# Start a new tmux session named mairs-training
tmux new -s mairs-training
```
*(In case your internet drops later, re-connect to the server and run `tmux attach -t mairs-training` to view live logs)*.

### 2. Activate Python Environment
```bash
source /root/ml-env/bin/activate
```

### 3. Execute the Standard Training Script
Run the custom training script utilizing the pre-processed train/val datasets:
```bash
python3 train.py
```

> [!TIP]
> **Optimizing VRAM on 24GB GPUs (A10G)**
> If you experience `CUDA Out Of Memory (OOM)` errors, modify `train.py` training arguments to enable **8-bit Quantized training** (via `bitsandbytes`) or lower sequence lengths:
> - In `train.py`, set:
>   `per_device_train_batch_size=2` (down from 4)
>   `gradient_accumulation_steps=8` (up from 4, keeping effective batch size = 16)
> - Switch from standard Loading to 4-Bit QLoRA configuration.

### QLoRA (4-bit) Training Configuration Code
If you want to modify `train.py` to use minimal VRAM (around ~11GB of VRAM, perfect for budget cards):
```python
from transformers import BitsAndBytesConfig
import torch

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map="auto"
)
```

---

## 💾 Section 6: Exporting Weights & Server Destruction

Once the `train.py` script completes, it will save the trained adapter weights under `mairs-llama-3.1-8b` (containing custom SRE logic).

### 1. Transfer Weights Locally
Exit your SSH session (or open a new terminal window on your local macOS computer) and pull the saved LoRA adapter model:
```bash
cd /Users/rauneetsingh/Developer/MAIRS/mairs-v2/fine_tuning/
scp -r root@<DROPLET_IP>:/root/fine_tuning/mairs-llama-3.1-8b .
```

### 2. Push directly to Hugging Face Hub (Optional, Droplet Terminal)
If you want to store the adapter in Hugging Face securely from the server:
```bash
# Install Hugging Face Hub CLI
pip install huggingface_hub

# Authenticate with your write-token
huggingface-cli login

# Run python script or command to upload the folder
python3 -c "
from huggingface_hub import HfApi
api = HfApi()
api.upload_folder(
    folder_path='/root/fine_tuning/mairs-llama-3.1-8b',
    repo_id='your_username/mairs-sre-qwen-adapter',
    repo_type='model'
)
"
```

### 3. ⚠️ IMPORTANT: Destroy Your DigitalOcean Droplet!
GPU instances are billed **hourly** ($0.50 to $4.00+ depending on GPU specs). Even if the server is stopped/powered-off, **you will still be billed for the reserved hardware, storage, and IP allocation!**

To stop charges:
1. Log in to the **DigitalOcean Cloud Dashboard**.
2. Locate your active GPU Droplet.
3. Click **More** ➔ **Destroy**.
4. Confirm destruction to release all cloud resources.
