# Ubuntu Core 24 Bare Metal Deployment Guide

## Overview

This guide covers deploying Ubuntu Core 24 with custom AI worker snaps to bare metal hardware, including automated provisioning and recovery procedures.

## Hardware Requirements

### Minimum Requirements
- CPU: x86_64 processor with virtualization support
- RAM: 4GB minimum, 16GB+ recommended for AI workloads
- Storage: 32GB minimum, 256GB+ SSD recommended
- Network: Ethernet connection
- GPU: NVIDIA GPU (optional but recommended for AI)

### Recommended AI Worker Configuration
- CPU: AMD Ryzen 9 or Intel Core i9
- RAM: 64GB+ DDR5
- Storage: 1TB+ NVMe SSD
- GPU: NVIDIA RTX 4090 or better
- Network: 10GbE connection

## Creating Ubuntu Core Image

### 1. Build Custom Snaps

```bash
cd /home/edward/network.worktrees/v2/ubuntu-core
./scripts/build-and-test-snaps.sh

# Select snaps to build:
# - ai-worker (or ai-worker-pro/ai-worker-budget)
# - ai-hardware-gadget
```

### 2. Create Model Assertion

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
    "storage-safety": "prefer-encrypted",
    "snaps": [
        {
            "name": "ai-hardware-gadget",
            "type": "gadget"
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
        },
        {
            "name": "ai-worker",
            "type": "app"
        }
    ]
}
```

### 3. Build Ubuntu Core Image

```bash
# For unsigned image (development)
ubuntu-image snap models/ai-worker-model.json \
    --channel stable \
    --snap snaps/ai-worker/ai-worker_1.0_amd64.snap \
    --snap snaps/ai-hardware-gadget/ai-hardware-gadget_1.0_amd64.snap \
    --output-dir images/ \
    --image-size 32G

# This creates: images/pc.img
```

## Deployment Methods

### Method 1: Direct Disk Write

```bash
# Identify target disk (BE VERY CAREFUL)
lsblk

# Write image to disk
sudo dd if=images/pc.img of=/dev/sdX bs=4M status=progress conv=fsync

# Where /dev/sdX is your target disk
```

### Method 2: USB Installation

1. Create bootable USB:
```bash
# Write to USB drive
sudo dd if=images/pc.img of=/dev/sdY bs=4M status=progress conv=fsync
```

2. Boot target machine from USB
3. Install to internal drive using Ubuntu Core installer

### Method 3: Network Boot (PXE)

1. Set up PXE server:

```bash
# Install required packages
sudo apt-get install dnsmasq pxelinux syslinux-common

# Configure dnsmasq
cat > /etc/dnsmasq.d/pxe.conf << EOF
interface=eth0
bind-interfaces
dhcp-range=192.168.1.100,192.168.1.200,12h
dhcp-boot=pxelinux.0
enable-tftp
tftp-root=/srv/tftp
EOF

# Set up TFTP directory
sudo mkdir -p /srv/tftp/ubuntu-core
sudo cp /usr/lib/PXELINUX/pxelinux.0 /srv/tftp/
sudo cp /usr/lib/syslinux/modules/bios/*.c32 /srv/tftp/
```

2. Extract kernel and initrd from Ubuntu Core image:

```bash
# Mount the image
sudo losetup -P /dev/loop10 images/pc.img
sudo mount /dev/loop10p3 /mnt

# Copy boot files
sudo cp /mnt/kernel.img /srv/tftp/ubuntu-core/
sudo cp /mnt/initrd.img /srv/tftp/ubuntu-core/

# Unmount
sudo umount /mnt
sudo losetup -d /dev/loop10
```

3. Create PXE menu:

```bash
sudo mkdir -p /srv/tftp/pxelinux.cfg
cat > /srv/tftp/pxelinux.cfg/default << EOF
DEFAULT ubuntu-core
TIMEOUT 50
PROMPT 1

LABEL ubuntu-core
    MENU LABEL Ubuntu Core 24 - AI Worker
    KERNEL ubuntu-core/kernel.img
    INITRD ubuntu-core/initrd.img
    APPEND console=ttyS0,115200n8 console=tty1
EOF
```

## Automated Provisioning

### Cloud-Init Configuration

Create `cloud-init/user-data`:

```yaml
#cloud-config
# Ubuntu Core 24 AI Worker Configuration

# Set hostname based on MAC address
hostname: ai-worker-${mac}

# Configure network
network:
  version: 2
  ethernets:
    eno1:
      dhcp4: true
      dhcp6: true
    eno2:
      dhcp4: false
      addresses: [10.0.0.${ip_suffix}/24]
      mtu: 9000

# Run commands on first boot
runcmd:
  # Configure GPU
  - nvidia-smi -pm 1
  - nvidia-smi -pl 450
  
  # Set up AI worker
  - snap set ai-worker ray-head-ip=10.0.0.1
  - snap set ai-worker worker-id=${hostname}
  
  # Start services
  - snap start ai-worker
  
# SSH keys
ssh_authorized_keys:
  - ssh-rsa YOUR_PUBLIC_KEY_HERE
```

### Zero-Touch Provisioning Script

```bash
#!/bin/bash
# zero-touch-provision.sh

# Get system information
MAC=$(ip link show | awk '/ether/ {print $2}' | head -1 | tr ':' '-')
HOSTNAME="ai-worker-$MAC"

# Configure system
hostnamectl set-hostname "$HOSTNAME"

# Auto-detect hardware
GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l || echo 0)
CPU_MODEL=$(lscpu | grep "Model name" | cut -d: -f2 | xargs)
MEMORY_GB=$(($(free -b | awk '/^Mem:/{print $2}') / 1024 / 1024 / 1024))

# Report to management server
curl -X POST http://management-server:8080/api/register \
  -H "Content-Type: application/json" \
  -d "{
    \"hostname\": \"$HOSTNAME\",
    \"mac\": \"$MAC\",
    \"gpu_count\": $GPU_COUNT,
    \"cpu_model\": \"$CPU_MODEL\",
    \"memory_gb\": $MEMORY_GB
  }"

# Configure based on hardware
if [ $GPU_COUNT -gt 0 ]; then
    snap set ai-worker profile=gpu-worker
else
    snap set ai-worker profile=cpu-worker
fi
```

## Recovery Procedures

### 1. Create Recovery System

```bash
# On management server
snapd-remote-client.py \
  --host ai-worker-001 \
  --command create-recovery \
  --label "ai-worker-recovery-$(date +%Y%m%d)" \
  --validation-sets "ai-worker-stable"
```

### 2. Factory Reset

Boot into recovery mode and select "Factory Reset" option, or:

```bash
# Remote factory reset
sudo snap reboot --factory-reset
```

### 3. Emergency Recovery

If system won't boot:

1. Boot from Ubuntu Core USB
2. Mount system partitions:
```bash
mkdir -p /tmp/recovery
mount /dev/sda3 /tmp/recovery
```

3. Restore from backup:
```bash
# Restore snap data
tar -xzf /backup/snapdata-backup.tar.gz -C /tmp/recovery/
```

4. Fix boot loader:
```bash
grub-install --target=x86_64-efi --efi-directory=/tmp/recovery/boot/efi
update-grub
```

## Mass Deployment

### Deploy to Multiple Nodes

```bash
#!/bin/bash
# mass-deploy.sh

NODES=(
    "192.168.1.101"
    "192.168.1.102"
    "192.168.1.103"
    "192.168.1.104"
)

IMAGE_FILE="images/pc.img"

for node in "${NODES[@]}"; do
    echo "Deploying to $node..."
    
    # Use Clonezilla over network
    ssh root@$node "
        # Download image
        wget http://image-server/ubuntu-core-ai.img
        
        # Write to disk
        dd if=ubuntu-core-ai.img of=/dev/sda bs=4M status=progress
        
        # Configure unique settings
        mount /dev/sda3 /mnt
        echo $node > /mnt/etc/hostname
        umount /mnt
        
        # Reboot
        reboot
    "
done
```

### Ansible Playbook

```yaml
---
- name: Deploy Ubuntu Core to AI Workers
  hosts: ai_workers
  become: yes
  
  tasks:
    - name: Download Ubuntu Core image
      get_url:
        url: http://image-server/ubuntu-core-ai.img
        dest: /tmp/ubuntu-core.img
        
    - name: Write image to disk
      command: dd if=/tmp/ubuntu-core.img of=/dev/sda bs=4M
      
    - name: Configure hostname
      mount:
        path: /mnt
        src: /dev/sda3
        fstype: ext4
        state: mounted
        
    - name: Set hostname
      copy:
        content: "{{ inventory_hostname }}"
        dest: /mnt/etc/hostname
        
    - name: Unmount
      mount:
        path: /mnt
        state: unmounted
        
    - name: Reboot
      reboot:
```

## Post-Deployment Configuration

### 1. Verify Installation

```bash
# Check system status
ssh ubuntu@ai-worker-001

# Verify Ubuntu Core
snap version

# Check AI worker
snap services ai-worker
ai-worker.ai-ctl status
```

### 2. Configure Networking

```bash
# Set static IP if needed
sudo netplan set ethernets.eno1.addresses=[192.168.1.101/24]
sudo netplan set ethernets.eno1.gateway4=192.168.1.1
sudo netplan apply
```

### 3. Join AI Cluster

```bash
# Configure Ray cluster
snap set ai-worker ray-head-ip=192.168.1.100
snap restart ai-worker.ray-worker

# Verify connection
ai-worker.ai-ctl status
```

## Hardware-Specific Configuration

### NVIDIA GPU Setup

```bash
# Install NVIDIA drivers (if not included)
sudo snap install nvidia-core24

# Configure GPU
nvidia-smi -pm 1  # Persistence mode
nvidia-smi -pl 450  # Power limit
nvidia-smi -ac 1215,1410  # Application clocks
```

### AMD GPU Setup

```bash
# Install ROCm runtime
sudo snap install rocm-runtime

# Configure GPU
rocm-smi --setperflevel high
rocm-smi --setfan 80
```

## Troubleshooting

### Boot Issues

1. **System won't boot**: Check UEFI/BIOS settings, ensure Secure Boot is configured correctly
2. **Kernel panic**: Boot with `init=/bin/bash` to debug
3. **Network not working**: Check `/etc/netplan/` configuration

### Snap Issues

```bash
# Debug snap installation
journalctl -u snapd

# Check snap logs
snap logs ai-worker

# Reinstall snap
snap remove ai-worker
snap install ai-worker
```

### Performance Issues

```bash
# Check resource usage
htop
nvidia-smi dmon

# Check thermal throttling
sensors
nvidia-smi -q -d TEMPERATURE

# Optimize CPU governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## Security Hardening

### 1. Enable Full Disk Encryption

```bash
# During image creation
ubuntu-image snap model.assert \
    --channel stable \
    --output-dir images/ \
    --disk-encryption
```

### 2. Configure Firewall

```bash
# Install ufw snap
sudo snap install ufw

# Configure rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 6379/tcp  # Ray
sudo ufw allow 8080/tcp  # Monitoring
sudo ufw enable
```

### 3. Regular Updates

```bash
# Enable automatic updates
sudo snap set system refresh.schedule=02:00-04:00

# Or manual update
sudo snap refresh
```

This completes the bare metal deployment guide for Ubuntu Core 24 with AI worker capabilities.