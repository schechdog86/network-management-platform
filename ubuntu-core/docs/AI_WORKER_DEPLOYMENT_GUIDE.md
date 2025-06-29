# AI Worker Snap Deployment Guide

## Overview

This guide provides step-by-step instructions for building, testing, and deploying the AI worker snap on Ubuntu Core 24 for your local AI training cluster.

## Prerequisites

- Ubuntu 22.04 LTS or later development machine
- Snapcraft installed (`sudo snap install snapcraft --classic`)
- Ubuntu-image tool installed (`sudo snap install ubuntu-image --classic`)
- Target hardware with NVIDIA or AMD GPUs
- Network connectivity to Ray head node

## Building the AI Worker Snap

### 1. Navigate to the snap directory

```bash
cd /home/edward/network.worktrees/v2/ubuntu-core/snaps/ai-worker
```

### 2. Build the snap

```bash
# Clean build
snapcraft clean

# Build the snap
snapcraft

# This will create: ai-worker_1.0_amd64.snap
```

### 3. Test locally (on development machine)

```bash
# Install in devmode for testing
sudo snap install ai-worker_1.0_amd64.snap --devmode --dangerous

# Check installation
snap list | grep ai-worker

# Test the CLI tool
ai-worker.ai-ctl status

# View logs
sudo journalctl -u snap.ai-worker.ray-worker -f
```

## Creating Ubuntu Core 24 Image for AI Workers

### 1. Create a model assertion

Create `models/ai-worker-model.json`:

```json
{
    "type": "model",
    "authority-id": "generic",
    "brand-id": "generic",
    "series": "16",
    "model": "ai-worker-uc24",
    "architecture": "amd64",
    "base": "core24",
    "grade": "dangerous",
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
            "name": "network-manager",
            "type": "app"
        }
    ]
}
```

### 2. Build the Ubuntu Core image

```bash
# For development/testing (unsigned)
ubuntu-image snap models/ai-worker-model.json \
    --channel stable \
    --output-dir images/ \
    --image-size 8G

# This creates: images/pc.img
```

### 3. Add the AI worker snap to the image

Since we're using a local snap, we need to inject it after installation:

```bash
# Mount the image
sudo mkdir -p /mnt/ubuntu-core
sudo losetup -P /dev/loop10 images/pc.img
sudo mount /dev/loop10p3 /mnt/ubuntu-core

# Copy the snap
sudo cp ai-worker_1.0_amd64.snap /mnt/ubuntu-core/var/lib/snapd/seed/snaps/

# Create assertion (for development)
cat > ai-worker.assert << EOF
type: snap-declaration
authority-id: generic
series: 16
snap-id: ai-worker-snap-id
snap-name: ai-worker
publisher-id: generic
EOF

sudo cp ai-worker.assert /mnt/ubuntu-core/var/lib/snapd/seed/assertions/

# Unmount
sudo umount /mnt/ubuntu-core
sudo losetup -d /dev/loop10
```

## Deployment Methods

### Method 1: Direct Disk Write (Recommended for bare metal)

```bash
# Write to target disk (BE CAREFUL - this will erase the disk!)
sudo dd if=images/pc.img of=/dev/sdX bs=4M status=progress conv=fsync

# Where /dev/sdX is your target disk
```

### Method 2: Network Boot (PXE)

1. Extract kernel and initrd from the image:

```bash
# Mount the image
sudo losetup -P /dev/loop10 images/pc.img
sudo mount /dev/loop10p1 /mnt/ubuntu-core

# Copy files
cp /mnt/ubuntu-core/kernel.efi /srv/tftp/ubuntu-core/
cp /mnt/ubuntu-core/initrd.img /srv/tftp/ubuntu-core/

# Unmount
sudo umount /mnt/ubuntu-core
sudo losetup -d /dev/loop10
```

2. Configure PXE server to boot Ubuntu Core

### Method 3: USB Installation

```bash
# Create bootable USB
sudo dd if=images/pc.img of=/dev/sdX bs=4M status=progress conv=fsync

# Boot target machine from USB
```

## First Boot Configuration

### 1. Initial Setup

On first boot, Ubuntu Core will:
- Generate SSH keys
- Configure network (DHCP by default)
- Start snapd services

### 2. Connect via SSH

```bash
# Find the IP address (check DHCP server or use nmap)
nmap -sn 192.168.1.0/24

# SSH to the device (default user: ubuntu)
ssh ubuntu@<device-ip>
```

### 3. Configure the AI Worker

```bash
# Set Ray head address
sudo snap set ai-worker ray-head-ip=192.168.1.100

# Enable GPU monitoring
sudo snap set ai-worker enable-gpu-monitoring=true

# Set model cache size
sudo snap set ai-worker model-cache-size=100G

# Restart services
sudo snap restart ai-worker
```

### 4. Verify Installation

```bash
# Check snap status
snap list

# Check service status
systemctl status snap.ai-worker.ray-worker

# View worker status
ai-worker.ai-ctl status

# Test GPU
ai-worker.ai-ctl test-gpu

# Check Ray connection
ray status
```

## Mass Deployment Script

For deploying to multiple nodes:

```bash
#!/bin/bash
# deploy-ai-workers.sh

WORKER_IPS=(
    "192.168.1.101"
    "192.168.1.102"
    "192.168.1.103"
    "192.168.1.104"
)

IMAGE_FILE="images/pc.img"
RAY_HEAD="192.168.1.100"

for ip in "${WORKER_IPS[@]}"; do
    echo "Deploying to $ip..."
    
    # Copy image to worker (requires root SSH access)
    scp $IMAGE_FILE root@$ip:/tmp/
    
    # Write image to disk
    ssh root@$ip "dd if=/tmp/pc.img of=/dev/sda bs=4M status=progress && sync && reboot"
    
    echo "Waiting for reboot..."
    sleep 120
    
    # Configure worker
    ssh ubuntu@$ip << EOF
        sudo snap set ai-worker ray-head-ip=$RAY_HEAD
        sudo snap restart ai-worker
EOF
    
    echo "✓ Worker $ip deployed"
done
```

## Monitoring and Management

### 1. Central Monitoring

Create a monitoring dashboard to track all workers:

```python
#!/usr/bin/env python3
# monitor-workers.py

import requests
import json
from datetime import datetime

WORKERS = [
    "192.168.1.101",
    "192.168.1.102",
    "192.168.1.103",
    "192.168.1.104"
]

def get_worker_stats(ip):
    try:
        # Get stats from worker API
        response = requests.get(f"http://{ip}:8080/stats", timeout=5)
        return response.json()
    except:
        return None

def main():
    print(f"AI Worker Cluster Status - {datetime.now()}")
    print("=" * 60)
    
    total_gpus = 0
    total_memory = 0
    
    for worker_ip in WORKERS:
        stats = get_worker_stats(worker_ip)
        if stats:
            gpu_count = len(stats.get('gpus', []))
            total_gpus += gpu_count
            
            print(f"\nWorker: {worker_ip}")
            print(f"  Status: Online")
            print(f"  GPUs: {gpu_count}")
            print(f"  CPU Usage: {stats['system']['cpu_percent']:.1f}%")
            print(f"  Memory Usage: {stats['system']['memory']['percent']:.1f}%")
            
            for gpu in stats.get('gpus', []):
                print(f"  GPU {gpu['index']}: {gpu['gpu_utilization']}% util, {gpu['temperature']}°C")
        else:
            print(f"\nWorker: {worker_ip}")
            print(f"  Status: Offline")
    
    print(f"\nCluster Total:")
    print(f"  Workers: {len(WORKERS)}")
    print(f"  Total GPUs: {total_gpus}")

if __name__ == '__main__':
    main()
```

### 2. Remote Management via Snapd API

```bash
# Update all workers
for ip in 192.168.1.{101..104}; do
    curl -X POST http://$ip:8000/v2/snaps/ai-worker \
        -H "Content-Type: application/json" \
        -d '{"action": "refresh"}'
done

# Check logs remotely
ssh ubuntu@192.168.1.101 "sudo journalctl -u snap.ai-worker.ray-worker -n 100"
```

## Troubleshooting

### Common Issues

1. **GPU not detected**
   ```bash
   # Check GPU drivers
   ubuntu-drivers devices
   
   # Install NVIDIA drivers snap
   sudo snap install nvidia-core24
   ```

2. **Ray connection failed**
   ```bash
   # Check network connectivity
   ping ray-head
   
   # Verify Ray head is running
   ray status --address ray-head:6379
   ```

3. **Insufficient permissions**
   ```bash
   # Connect required interfaces
   sudo snap connect ai-worker:gpu
   sudo snap connect ai-worker:hardware-observe
   ```

4. **Model cache issues**
   ```bash
   # Check cache status
   ai-worker.ai-ctl cache-info
   
   # Clean cache
   ai-worker.model-cache cleanup --force
   ```

### Debug Mode

Enable debug logging:

```bash
sudo snap set ai-worker log-level=DEBUG
sudo snap restart ai-worker
sudo journalctl -u snap.ai-worker.ray-worker -f
```

## Performance Optimization

### 1. GPU Optimization

```bash
# Set GPU to persistence mode
sudo nvidia-smi -pm 1

# Set maximum performance
sudo nvidia-smi -pl 300  # Set power limit (watts)

# Configure GPU clocks
sudo nvidia-smi -ac 877,1380  # Memory,Graphics clocks
```

### 2. Network Optimization

Edit `/etc/netplan/00-installer-config.yaml`:

```yaml
network:
  version: 2
  ethernets:
    eno1:
      mtu: 9000  # Enable jumbo frames
      dhcp4: false
      addresses: [192.168.1.101/24]
```

Apply changes:
```bash
sudo netplan apply
```

### 3. System Tuning

Create `/etc/sysctl.d/99-ai-worker.conf`:

```bash
# Increase network buffers
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# Disable swap
vm.swappiness = 0

# Increase file descriptors
fs.file-max = 2097152
```

Apply:
```bash
sudo sysctl -p /etc/sysctl.d/99-ai-worker.conf
```

## Security Considerations

1. **Network Isolation**: Place AI workers on dedicated VLAN
2. **Firewall Rules**: Only allow necessary ports (Ray, monitoring)
3. **SSH Keys**: Use key-based authentication only
4. **Snap Confinement**: Keep snaps in strict confinement
5. **Regular Updates**: Enable automatic security updates

## Next Steps

1. Deploy to production hardware
2. Integrate with Ray cluster
3. Set up monitoring dashboards
4. Configure automated backups
5. Implement model versioning
6. Create CI/CD pipeline for snap updates

This setup provides a robust, scalable platform for AI workloads with the security and reliability benefits of Ubuntu Core 24.