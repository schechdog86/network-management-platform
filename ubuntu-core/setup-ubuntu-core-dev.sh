#!/bin/bash
# Ubuntu Core 24 Development Environment Setup Script
# Based on research from official Ubuntu Core 24 documentation

set -e

echo "=== Ubuntu Core 24 Development Environment Setup ==="
echo "This script will set up the development environment for Ubuntu Core 24"
echo ""

# Check if running on Ubuntu
if ! grep -q "Ubuntu" /etc/os-release; then
    echo "Warning: This script is designed for Ubuntu. Some commands may need adjustment for other distributions."
fi

# Step 1: Install Snapcraft
echo "Step 1: Installing Snapcraft..."
if ! command -v snapcraft &> /dev/null; then
    sudo snap install snapcraft --classic
    echo "✓ Snapcraft installed successfully"
else
    echo "✓ Snapcraft is already installed"
fi

# Step 2: Install Ubuntu Image tool
echo ""
echo "Step 2: Installing ubuntu-image tool..."
if ! command -v ubuntu-image &> /dev/null; then
    sudo snap install ubuntu-image --classic
    echo "✓ ubuntu-image installed successfully"
else
    echo "✓ ubuntu-image is already installed"
fi

# Step 3: Install additional development tools
echo ""
echo "Step 3: Installing additional development tools..."
sudo apt-get update
sudo apt-get install -y \
    git \
    build-essential \
    qemu-system-x86 \
    qemu-user-static \
    lxd \
    multipass \
    curl \
    wget \
    python3-pip \
    python3-venv

echo "✓ Development tools installed"

# Step 4: Initialize LXD for container testing
echo ""
echo "Step 4: Initializing LXD for container testing..."
if ! groups | grep -q lxd; then
    sudo usermod -aG lxd $USER
    echo "Added user to lxd group. You may need to log out and back in."
fi

# Step 5: Install Multipass for VM testing
echo ""
echo "Step 5: Setting up Multipass..."
if ! command -v multipass &> /dev/null; then
    sudo snap install multipass
    echo "✓ Multipass installed successfully"
else
    echo "✓ Multipass is already installed"
fi

# Step 6: Create development directory structure
echo ""
echo "Step 6: Creating development directory structure..."
mkdir -p ~/ubuntu-core-dev/{snaps,images,models,gadgets}
echo "✓ Created development directories at ~/ubuntu-core-dev"

# Step 7: Download Core 24 base
echo ""
echo "Step 7: Ensuring Core 24 base is available..."
sudo snap download core24
echo "✓ Core 24 base downloaded"

# Step 8: Create example snapcraft.yaml template
echo ""
echo "Step 8: Creating example snap template..."
cat > ~/ubuntu-core-dev/snaps/hello-core24/snapcraft.yaml << 'EOF'
name: hello-core24
version: '1.0'
summary: Hello World snap for Ubuntu Core 24
description: |
  A simple hello world snap to test Ubuntu Core 24 development.
  This snap demonstrates basic snap packaging for Core 24.

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
EOF

# Create the hello script
mkdir -p ~/ubuntu-core-dev/snaps/hello-core24
cat > ~/ubuntu-core-dev/snaps/hello-core24/hello.sh << 'EOF'
#!/bin/bash
echo "Hello from Ubuntu Core 24!"
echo "System info:"
uname -a
echo ""
echo "Snap info:"
snap version
EOF

chmod +x ~/ubuntu-core-dev/snaps/hello-core24/hello.sh

echo "✓ Created example snap template"

# Step 9: Show helpful information
echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Development environment for Ubuntu Core 24 is ready."
echo ""
echo "Directory structure created at: ~/ubuntu-core-dev/"
echo "  - snaps/    : For snap development"
echo "  - images/   : For built Ubuntu Core images"
echo "  - models/   : For model assertions"
echo "  - gadgets/  : For gadget snap development"
echo ""
echo "Next steps:"
echo "1. cd ~/ubuntu-core-dev/snaps/hello-core24"
echo "2. snapcraft  # Build your first snap"
echo "3. sudo snap install hello-core24_1.0_amd64.snap --dangerous"
echo "4. hello-core24.hello  # Test the snap"
echo ""
echo "To create an Ubuntu Core 24 VM:"
echo "  multipass launch --name uc24-test --cpus 2 --memory 2G --disk 10G"
echo ""
echo "For Ubuntu Core image building, refer to:"
echo "  https://documentation.ubuntu.com/core/tutorials/build-your-first-image/"
echo ""
echo "Note: If you were added to the lxd group, log out and back in for changes to take effect."