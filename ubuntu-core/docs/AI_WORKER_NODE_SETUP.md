# Ubuntu Core 24 for AI Worker Nodes

## Overview

This guide details how to set up Ubuntu Core 24 as a lightweight, secure, and efficient operating system for AI worker nodes in your local AI training and inference cluster. Ubuntu Core's immutable design and snap packaging make it ideal for deploying consistent, reliable AI worker nodes.

## Key Benefits for AI Workloads

1. **Immutable OS**: Prevents configuration drift across worker nodes
2. **Atomic Updates**: Zero-downtime updates with automatic rollback
3. **Minimal Footprint**: More resources available for AI workloads
4. **GPU Support**: Native support for NVIDIA and AMD GPUs
5. **Container-Ready**: Excellent integration with Docker and Kubernetes
6. **Remote Management**: REST API for cluster management
7. **12-Year LTS**: Long-term stability for production AI systems

## Architecture for AI Cluster

```
AI Cluster Architecture with Ubuntu Core 24:
├── Control Node (Ubuntu 24.04 LTS)
│   ├── Ray Head Node
│   ├── Kubernetes Master
│   ├── Model Registry
│   └── Management Dashboard
└── Worker Nodes (Ubuntu Core 24)
    ├── AI Worker Snap
    │   ├── Ray Worker
    │   ├── PyTorch/TensorFlow
    │   ├── CUDA/ROCm Runtime
    │   └── Model Cache
    ├── GPU Driver Snap
    ├── Monitoring Snap
    └── Container Runtime Snap
```

## AI Worker Snap Development

### Create AI Worker Snap Structure

```bash
mkdir -p /home/edward/network.worktrees/v2/ubuntu-core/snaps/ai-worker
cd /home/edward/network.worktrees/v2/ubuntu-core/snaps/ai-worker
```

### AI Worker Snapcraft Configuration

Create `snapcraft.yaml`:

```yaml
name: ai-worker
version: '1.0'
summary: AI Worker Node for distributed training and inference
description: |
  A comprehensive AI worker node snap that includes Ray, PyTorch,
  TensorFlow, and GPU support for distributed AI workloads.
  Optimized for Ubuntu Core 24 deployment.

base: core24
grade: stable
confinement: strict

architectures:
  - build-on: amd64
    run-on: amd64

# Environment variables for AI libraries
environment:
  PYTHONPATH: $SNAP/usr/lib/python3/dist-packages:$PYTHONPATH
  LD_LIBRARY_PATH: $SNAP/usr/local/cuda/lib64:$LD_LIBRARY_PATH
  CUDA_HOME: $SNAP/usr/local/cuda
  RAY_ADDRESS: "auto"

# Define slots for GPU access
slots:
  gpu-support:
    interface: content
    content: gpu-driver
    write:
      - $SNAP_DATA/gpu

# Required plugs for AI workloads
plugs:
  gpu:
    interface: opengl
  cuda:
    interface: content
    content: cuda-runtime
    target: $SNAP/cuda
  network:
  network-bind:
  home:
  removable-media:
  hardware-observe:
  system-observe:
  process-control:
  mount-observe:

apps:
  # Main Ray worker daemon
  ray-worker:
    command: bin/start-ray-worker
    daemon: simple
    restart-condition: always
    plugs:
      - network
      - network-bind
      - gpu
      - cuda
      - hardware-observe
      - system-observe
      - process-control

  # PyTorch training service
  pytorch-worker:
    command: bin/pytorch-worker
    daemon: simple
    restart-condition: always
    plugs:
      - network
      - gpu
      - cuda
      - home

  # TensorFlow serving
  tf-serving:
    command: bin/tensorflow-serving
    daemon: simple
    restart-condition: always
    plugs:
      - network
      - network-bind
      - gpu
      - cuda

  # Model cache manager
  model-cache:
    command: bin/model-cache-manager
    daemon: simple
    plugs:
      - network
      - home
      - removable-media

  # Performance monitor
  monitor:
    command: bin/gpu-monitor
    daemon: simple
    plugs:
      - hardware-observe
      - system-observe
      - gpu

parts:
  # Python AI libraries
  ai-libs:
    plugin: python
    source: .
    python-packages:
      - ray[default]==2.9.0
      - torch==2.1.2
      - torchvision==0.16.2
      - tensorflow==2.15.0
      - numpy==1.24.3
      - pandas==2.0.3
      - scikit-learn==1.3.2
      - transformers==4.36.2
      - accelerate==0.25.0
      - datasets==2.16.1
      - tokenizers==0.15.0
      - safetensors==0.4.1
      - psutil==5.9.6
      - gpustat==1.1.1
      - nvidia-ml-py==12.535.133
    stage-packages:
      - python3-dev
      - python3-pip
      - libopenblas-dev
      - liblapack-dev
      - libhdf5-dev
      - libopenmpi-dev

  # GPU support libraries
  gpu-support:
    plugin: nil
    stage-packages:
      - ocl-icd-libopencl1
      - opencl-headers
      - clinfo
      - libgomp1
      - libnuma1

  # Worker scripts
  scripts:
    plugin: dump
    source: scripts/
    organize:
      '*.sh': bin/
      '*.py': bin/

  # Configuration files
  config:
    plugin: dump
    source: config/
    organize:
      '*': etc/ai-worker/

# Hooks for initialization
hooks:
  install:
    plugs: [network]
  configure:
    plugs: [network, gpu]
```

### Create Worker Scripts

Create `scripts/start-ray-worker.sh`:

```bash
#!/bin/bash
set -e

# Load configuration
source $SNAP/etc/ai-worker/worker.conf

# Wait for network
while ! ping -c 1 ${RAY_HEAD_IP:-ray-head} &> /dev/null; do
    echo "Waiting for network connectivity..."
    sleep 5
done

# Detect GPU capabilities
GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l || echo 0)
echo "Detected $GPU_COUNT GPUs"

# Set Ray resources based on hardware
if [ $GPU_COUNT -gt 0 ]; then
    RAY_RESOURCES="--num-gpus=$GPU_COUNT"
else
    RAY_RESOURCES="--num-cpus=$(nproc)"
fi

# Start Ray worker
echo "Starting Ray worker node..."
ray start \
    --address="${RAY_HEAD_IP:-ray-head}:6379" \
    --node-ip-address="$(hostname -I | awk '{print $1}')" \
    $RAY_RESOURCES \
    --object-store-memory=$(($(free -b | awk '/^Mem:/{print $2}') * 3 / 10)) \
    --temp-dir=$SNAP_DATA/ray \
    --metrics-export-port=8080 \
    --block
```

Create `scripts/gpu-monitor.py`:

```python
#!/usr/bin/env python3
"""GPU monitoring service for AI worker nodes"""

import time
import json
import psutil
import socket
from datetime import datetime

try:
    import nvidia_ml_py as nvml
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False

class GPUMonitor:
    def __init__(self):
        if NVIDIA_AVAILABLE:
            nvml.nvmlInit()
            self.gpu_count = nvml.nvmlDeviceGetCount()
        else:
            self.gpu_count = 0
        
        self.hostname = socket.gethostname()
        
    def get_gpu_stats(self):
        """Collect GPU statistics"""
        stats = []
        
        if not NVIDIA_AVAILABLE or self.gpu_count == 0:
            return stats
            
        for i in range(self.gpu_count):
            handle = nvml.nvmlDeviceGetHandleByIndex(i)
            
            # Get GPU information
            name = nvml.nvmlDeviceGetName(handle).decode('utf-8')
            memory = nvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
            temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
            power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to watts
            
            stats.append({
                'index': i,
                'name': name,
                'memory_used': memory.used,
                'memory_total': memory.total,
                'memory_percent': (memory.used / memory.total) * 100,
                'gpu_utilization': utilization.gpu,
                'memory_utilization': utilization.memory,
                'temperature': temperature,
                'power_watts': power
            })
            
        return stats
    
    def get_system_stats(self):
        """Collect system statistics"""
        return {
            'hostname': self.hostname,
            'timestamp': datetime.utcnow().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'network_io': psutil.net_io_counters()._asdict()
        }
    
    def run(self):
        """Main monitoring loop"""
        while True:
            try:
                stats = {
                    'system': self.get_system_stats(),
                    'gpus': self.get_gpu_stats()
                }
                
                # Write to log file
                with open(f"{os.environ.get('SNAP_DATA', '.')}/gpu-stats.json", 'w') as f:
                    json.dump(stats, f, indent=2)
                
                # Also log to stdout for journald
                print(json.dumps(stats))
                
            except Exception as e:
                print(f"Error collecting stats: {e}")
                
            time.sleep(30)  # Collect stats every 30 seconds

if __name__ == '__main__':
    monitor = GPUMonitor()
    monitor.run()
```

### Create Configuration Files

Create `config/worker.conf`:

```bash
# AI Worker Node Configuration

# Ray cluster settings
RAY_HEAD_IP=192.168.1.100
RAY_HEAD_PORT=6379
RAY_OBJECT_STORE_SIZE=auto

# Model cache settings
MODEL_CACHE_DIR=$SNAP_COMMON/models
MODEL_CACHE_SIZE=50G

# GPU settings
CUDA_VISIBLE_DEVICES=all
TF_GPU_THREAD_MODE=gpu_private
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Performance tuning
OMP_NUM_THREADS=auto
MKL_NUM_THREADS=auto
NUMEXPR_NUM_THREADS=auto

# Monitoring
ENABLE_GPU_MONITORING=true
METRICS_PORT=8080
LOG_LEVEL=INFO
```

## Gadget Snap for AI Hardware

Create a custom gadget snap for AI-optimized hardware:

```yaml
# gadget.yaml for AI worker nodes
volumes:
  pc:
    bootloader: grub
    structure:
      - name: ubuntu-seed
        role: system-seed
        filesystem: vfat
        type: EF,C12A7328-F81F-11D2-BA4B-00A0C93EC93B
        size: 1200M
        content:
          - source: grub.conf
            target: EFI/ubuntu/grub.cfg
      
      - name: ubuntu-save
        role: system-save
        filesystem: ext4
        type: 83,0FC63DAF-8483-4772-8E79-3D69D8477DE4
        size: 32M
      
      - name: ubuntu-data
        role: system-data
        filesystem: ext4
        type: 83,0FC63DAF-8483-4772-8E79-3D69D8477DE4
        # Use remaining disk space for data
        size: 100%

defaults:
  # System configuration
  system:
    kernel:
      dangerous-cmdline: "intel_iommu=on iommu=pt"
    
    # Network configuration for cluster
    network:
      version: 2
      ethernets:
        # Management network
        eno1:
          dhcp4: false
          addresses: [192.168.1.0/24]
          nameservers:
            addresses: [8.8.8.8, 8.8.4.4]
        
        # High-speed interconnect for AI workloads
        eno2:
          dhcp4: false
          addresses: [10.0.0.0/24]
          mtu: 9000  # Jumbo frames for better throughput

  # AI worker configuration
  ai-worker:
    ray-head: "192.168.1.100:6379"
    enable-gpu: true
    cache-models: true
    monitoring: true
```

## Building the AI Worker Image

### 1. Create Model Assertion

Create `models/ai-worker-model.json`:

```json
{
    "type": "model",
    "authority-id": "YOUR-DEVELOPER-ID",
    "brand-id": "YOUR-DEVELOPER-ID",
    "series": "16",
    "model": "ai-worker-node",
    "architecture": "amd64",
    "base": "core24",
    "grade": "signed",
    "storage-safety": "prefer-encrypted",
    "snaps": [
        {
            "name": "pc",
            "type": "gadget",
            "default-channel": "24/stable"
        },
        {
            "name": "pc-kernel",
            "type": "kernel",
            "default-channel": "24/stable"
        },
        {
            "name": "core24",
            "type": "base"
        },
        {
            "name": "snapd",
            "type": "snapd"
        },
        {
            "name": "ai-worker",
            "type": "app"
        },
        {
            "name": "docker",
            "type": "app"
        },
        {
            "name": "microk8s",
            "type": "app",
            "classic": false
        }
    ]
}
```

### 2. Build Custom Image

```bash
# Build the AI worker snap
cd ubuntu-core/snaps/ai-worker
snapcraft

# Sign the model
cat models/ai-worker-model.json | snap sign -k ai-key > ai-worker.model

# Build the image
ubuntu-image snap ai-worker.model \
    --channel stable \
    --snap ai-worker_1.0_amd64.snap \
    --output-dir images/
```

## Deployment Script

Create `deploy-ai-worker.sh`:

```bash
#!/bin/bash
# Deploy Ubuntu Core 24 to AI worker nodes

set -e

WORKER_IMAGE="images/ai-worker.img"
WORKER_NODES=("worker1" "worker2" "worker3" "worker4")

echo "=== Deploying Ubuntu Core 24 AI Workers ==="

for node in "${WORKER_NODES[@]}"; do
    echo "Deploying to $node..."
    
    # Flash the image (adjust for your hardware)
    # This example assumes network boot or remote deployment
    ssh root@$node "dd if=/dev/zero of=/dev/sda bs=1M count=100"
    scp $WORKER_IMAGE root@$node:/tmp/
    ssh root@$node "dd if=/tmp/ai-worker.img of=/dev/sda bs=4M status=progress"
    ssh root@$node "sync && reboot"
    
    echo "✓ $node deployed"
done

echo "=== Deployment complete ==="
echo "Workers will auto-join the Ray cluster after boot"
```

## Management and Monitoring

### Remote Management via Snapd API

```python
#!/usr/bin/env python3
"""Manage AI worker fleet via snapd REST API"""

import requests
import json

class AIWorkerManager:
    def __init__(self, workers):
        self.workers = workers
        
    def get_worker_status(self, worker_ip):
        """Get status of AI worker snap"""
        response = requests.get(
            f"http://{worker_ip}:8000/v2/snaps/ai-worker",
            headers={"Content-Type": "application/json"}
        )
        return response.json()
    
    def update_worker(self, worker_ip):
        """Update AI worker snap"""
        response = requests.post(
            f"http://{worker_ip}:8000/v2/snaps/ai-worker",
            json={"action": "refresh"},
            headers={"Content-Type": "application/json"}
        )
        return response.json()
    
    def get_gpu_stats(self, worker_ip):
        """Get GPU statistics from worker"""
        response = requests.get(f"http://{worker_ip}:8080/metrics")
        return response.json()
    
    def manage_fleet(self):
        """Manage entire AI worker fleet"""
        for worker in self.workers:
            print(f"Checking {worker}...")
            status = self.get_worker_status(worker)
            print(f"  Status: {status['result']['status']}")
            
            gpu_stats = self.get_gpu_stats(worker)
            for gpu in gpu_stats.get('gpus', []):
                print(f"  GPU {gpu['index']}: {gpu['gpu_utilization']}% utilized")

# Example usage
manager = AIWorkerManager([
    "192.168.1.101",
    "192.168.1.102",
    "192.168.1.103",
    "192.168.1.104"
])
manager.manage_fleet()
```

## Performance Optimization

### 1. Kernel Parameters

Add to gadget snap for AI optimization:

```yaml
defaults:
  system:
    kernel:
      dangerous-cmdline: |
        intel_iommu=on 
        iommu=pt 
        pcie_aspm=off 
        processor.max_cstate=0 
        intel_idle.max_cstate=0
        transparent_hugepage=never
        numa_balancing=disable
```

### 2. GPU-Specific Optimizations

For NVIDIA GPUs:
```bash
# Set persistence mode
nvidia-smi -pm 1

# Set max performance
nvidia-smi -ac 877,1380  # A100 example

# Configure MIG for multi-instance GPU
nvidia-smi -mig 1
```

### 3. Network Optimization

Enable RDMA for distributed training:
```yaml
ai-worker:
  enable-rdma: true
  rdma-device: mlx5_0
  gdr-copy: true  # GPUDirect RDMA
```

## Integration with AI Frameworks

### Ray Cluster Integration

The AI worker automatically connects to Ray head node on boot:

```python
import ray

# Workers auto-connect using configuration
ray.init(address="auto")

# Submit distributed training job
@ray.remote(num_gpus=1)
def train_model(data_shard):
    import torch
    model = torch.nn.Linear(10, 1).cuda()
    # Training logic here
    return model.state_dict()

# Distribute across all workers
futures = [train_model.remote(shard) for shard in data_shards]
results = ray.get(futures)
```

### Kubernetes Integration

With microk8s included:

```bash
# Enable GPU support in microk8s
microk8s enable gpu

# Deploy AI workload
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  containers:
  - name: cuda-container
    image: nvidia/cuda:11.8.0-base-ubuntu22.04
    resources:
      limits:
        nvidia.com/gpu: 1
EOF
```

## Advantages for AI Workloads

1. **Consistency**: Every worker node identical configuration
2. **Security**: Immutable OS prevents tampering
3. **Reliability**: Automatic rollback on failed updates
4. **Efficiency**: Minimal OS overhead, more resources for AI
5. **Scalability**: Easy to deploy 100s of identical workers
6. **Management**: REST API for fleet management
7. **Updates**: Atomic updates across entire fleet

## Next Steps

1. Build and test the AI worker snap locally
2. Deploy to test hardware
3. Integrate with your Ray cluster
4. Set up monitoring dashboards
5. Create automated deployment pipeline

This Ubuntu Core 24 setup provides a robust, secure, and efficient platform for your AI worker nodes, with all the benefits of an immutable OS while maintaining full GPU acceleration capabilities.