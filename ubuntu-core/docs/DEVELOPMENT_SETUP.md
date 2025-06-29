# Ubuntu Core 24 Development Setup Guide

## Overview

This guide provides instructions for setting up a development environment for Ubuntu Core 24, including all necessary tools and a basic snap structure for the network management platform.

## Prerequisites

- Ubuntu 22.04 LTS or later (recommended)
- sudo access for installing packages
- At least 10GB of free disk space
- Internet connection for downloading packages

## Required Tools Installation

### 1. Install Snapcraft

Snapcraft is the primary tool for building snaps:

```bash
sudo snap install snapcraft --classic
```

### 2. Install Ubuntu Image

Ubuntu-image is used to create custom Ubuntu Core images:

```bash
sudo snap install ubuntu-image --classic
```

### 3. Install Development Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    git \
    build-essential \
    qemu-system-x86 \
    qemu-user-static \
    lxd \
    curl \
    wget \
    python3-pip \
    python3-venv \
    jq
```

### 4. Install Multipass (for VM testing)

```bash
sudo snap install multipass
```

### 5. Configure LXD (for container testing)

```bash
sudo lxd init --auto
sudo usermod -aG lxd $USER
# Log out and back in for group changes to take effect
```

## Directory Structure

The project uses the following directory structure:

```
ubuntu-core/
├── docs/               # Documentation
├── snaps/              # Snap packages
│   ├── network-mgmt-client/
│   ├── network-mgmt-server/
│   └── ray-cluster/
├── gadgets/            # Gadget snaps for hardware
├── models/             # Model assertions
└── images/             # Built Ubuntu Core images
```

## Ubuntu Core 24 Architecture

### Key Components

1. **Base Snap (core24)**: Provides the runtime environment based on Ubuntu 24.04
2. **Kernel Snap**: Contains the Linux kernel
3. **Gadget Snap**: Hardware-specific configuration and bootloader
4. **Application Snaps**: Your custom applications

### Snap Confinement

- **strict**: Full sandbox isolation (recommended for production)
- **devmode**: Relaxed permissions for development
- **classic**: Traditional filesystem access (not for Ubuntu Core)

## Building Your First Snap

### Example: Hello World Snap

Create a simple snap to test the environment:

```bash
cd ubuntu-core/snaps
mkdir -p hello-core24
cd hello-core24
```

Create `snapcraft.yaml`:

```yaml
name: hello-core24
version: '1.0'
summary: Hello World for Ubuntu Core 24
description: |
  A simple test snap for Ubuntu Core 24 development.

base: core24
grade: stable
confinement: strict

apps:
  hello:
    command: bin/hello
    plugs:
      - network

parts:
  hello:
    plugin: dump
    source: .
    organize:
      hello.sh: bin/hello
```

Create `hello.sh`:

```bash
#!/bin/bash
echo "Hello from Ubuntu Core 24!"
echo "System: $(uname -a)"
echo "Date: $(date)"
```

Make it executable:

```bash
chmod +x hello.sh
```

Build the snap:

```bash
snapcraft
```

Install and test:

```bash
sudo snap install hello-core24_1.0_amd64.snap --dangerous
hello-core24.hello
```

## Testing Ubuntu Core

### Using Multipass

Create an Ubuntu Core VM:

```bash
# Download Ubuntu Core 24 image
wget https://cdimage.ubuntu.com/ubuntu-core/24/stable/current/ubuntu-core-24-amd64.img.xz
xz -d ubuntu-core-24-amd64.img.xz

# Create VM with the image
multipass launch file://ubuntu-core-24-amd64.img --name uc24-test
```

### Using QEMU

```bash
qemu-system-x86_64 \
  -enable-kvm \
  -smp 2 \
  -m 2048 \
  -netdev user,id=net0,hostfwd=tcp::10022-:22 \
  -device virtio-net-pci,netdev=net0 \
  -drive file=ubuntu-core-24-amd64.img,format=raw \
  -nographic
```

## Creating Custom Ubuntu Core Images

### 1. Create a Model Assertion

Create `model.json`:

```json
{
    "type": "model",
    "series": "16",
    "model": "network-mgmt-core",
    "architecture": "amd64",
    "base": "core24",
    "grade": "dangerous",
    "snaps": [
        {
            "name": "pc",
            "type": "gadget"
        },
        {
            "name": "pc-kernel",
            "type": "kernel"
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
            "name": "network-mgmt-client",
            "type": "app"
        }
    ]
}
```

### 2. Sign the Model

```bash
# Create a key if you don't have one
snapcraft create-key network-mgmt
snapcraft register-key network-mgmt

# Sign the model
cat model.json | snap sign -k network-mgmt > model.assert
```

### 3. Build the Image

```bash
ubuntu-image snap model.assert \
  --channel edge \
  --output-dir images/
```

## Snapd REST API

Ubuntu Core provides a REST API for remote management:

### Basic API Usage

```bash
# Get system info
curl -s --unix-socket /run/snapd.socket http://localhost/v2/system-info | jq

# List installed snaps
curl -s --unix-socket /run/snapd.socket http://localhost/v2/snaps | jq

# Install a snap
curl -X POST --unix-socket /run/snapd.socket \
  -H "Content-Type: application/json" \
  -d '{"action": "install", "channel": "stable"}' \
  http://localhost/v2/snaps/hello
```

## Network Management Platform Snaps

### Client Snap Structure

```
network-mgmt-client/
├── snapcraft.yaml
├── src/
│   ├── agent.py           # Main client agent
│   ├── hardware_monitor.py # Hardware monitoring
│   ├── backup_client.py   # Backup functionality
│   └── ray_worker.py      # Ray cluster worker
├── hooks/
│   ├── install            # Post-install hook
│   └── configure          # Configuration hook
└── scripts/
    └── start-agent.sh     # Startup script
```

### Server Snap Structure

```
network-mgmt-server/
├── snapcraft.yaml
├── backend/               # FastAPI application
├── frontend/              # Web interface
├── database/              # Database schemas
└── scripts/
    ├── start-server.sh
    └── init-db.sh
```

## Development Workflow

1. **Develop locally**: Write and test code on regular Ubuntu
2. **Package as snap**: Use snapcraft to build snaps
3. **Test in devmode**: Install with `--devmode` for testing
4. **Test strict confinement**: Ensure proper interfaces
5. **Deploy to Ubuntu Core**: Test on actual Ubuntu Core system
6. **Iterate**: Fix issues and rebuild

## Debugging Tips

### Enable Debug Output

```bash
SNAPCRAFT_ENABLE_DEVELOPER_DEBUG=1 snapcraft
```

### Check Snap Logs

```bash
sudo journalctl -u snap.network-mgmt-client.agent
```

### Connect Interfaces

```bash
# List interfaces
snap connections network-mgmt-client

# Connect interface
sudo snap connect network-mgmt-client:network
```

### Shell into Snap Environment

```bash
snap run --shell network-mgmt-client.agent
```

## Security Best Practices

1. **Use strict confinement** in production
2. **Minimize interface usage** - only request needed permissions
3. **Sign all snaps** for production deployment
4. **Use secure communication** between client and server
5. **Implement proper authentication** in the management API

## Next Steps

1. Review the [SNAP_DEVELOPMENT.md](./SNAP_DEVELOPMENT.md) for detailed snap creation
2. Check [GADGET_CUSTOMIZATION.md](./GADGET_CUSTOMIZATION.md) for hardware-specific configuration
3. See [API_INTEGRATION.md](./API_INTEGRATION.md) for snapd REST API usage
4. Read [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for production deployment

## Resources

- [Ubuntu Core Documentation](https://ubuntu.com/core/docs)
- [Snapcraft Documentation](https://snapcraft.io/docs)
- [Ubuntu Core 24 Release Notes](https://documentation.ubuntu.com/core/reference/release-notes/)
- [Snapcraft Forum](https://forum.snapcraft.io/)
- [Ubuntu Core GitHub](https://github.com/canonical/ubuntu-image)