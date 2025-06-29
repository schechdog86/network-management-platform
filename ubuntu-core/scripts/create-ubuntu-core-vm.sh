#!/bin/bash
# Script to create Ubuntu Core 24 test VM

set -e

echo "=== Ubuntu Core 24 VM Creation Script ==="
echo "This script will create a test VM for Ubuntu Core 24 development"
echo ""

# Configuration
VM_NAME="ubuntu-core-24-test"
VM_DISK_SIZE="20G"
VM_MEMORY="4096"
VM_CPUS="2"
WORK_DIR="$HOME/ubuntu-core-vm"
IMAGE_URL="https://cdimage.ubuntu.com/ubuntu-core/24/stable/current/ubuntu-core-24-amd64.img.xz"

# Create work directory
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Download Ubuntu Core image if not present
if [ ! -f "ubuntu-core-24-amd64.img" ]; then
    echo "Downloading Ubuntu Core 24 image..."
    if [ ! -f "ubuntu-core-24-amd64.img.xz" ]; then
        wget "$IMAGE_URL"
    fi
    echo "Extracting image..."
    xz -d ubuntu-core-24-amd64.img.xz
fi

# Option 1: Using QEMU/KVM
setup_qemu_vm() {
    echo ""
    echo "=== Setting up QEMU/KVM VM ==="
    
    # Check if KVM is available
    if [ -r /dev/kvm ]; then
        KVM_OPTS="-enable-kvm"
        echo "KVM acceleration available"
    else
        KVM_OPTS=""
        echo "Warning: KVM not available, VM will be slower"
    fi
    
    # Create a copy of the image for the VM
    cp ubuntu-core-24-amd64.img "$VM_NAME.img"
    
    # Resize the image
    qemu-img resize "$VM_NAME.img" "$VM_DISK_SIZE"
    
    # Create start script
    cat > "start-$VM_NAME.sh" << EOF
#!/bin/bash
qemu-system-x86_64 \\
    $KVM_OPTS \\
    -name "$VM_NAME" \\
    -m "$VM_MEMORY" \\
    -smp "$VM_CPUS" \\
    -drive file="$VM_NAME.img",format=raw \\
    -netdev user,id=net0,hostfwd=tcp::10022-:22,hostfwd=tcp::8111-:8111 \\
    -device virtio-net-pci,netdev=net0 \\
    -nographic \\
    -serial mon:stdio
EOF
    
    chmod +x "start-$VM_NAME.sh"
    
    echo "VM created. Start with: ./start-$VM_NAME.sh"
    echo "SSH will be available on port 10022 after initial setup"
}

# Option 2: Using Multipass
setup_multipass_vm() {
    echo ""
    echo "=== Setting up Multipass VM ==="
    
    # Check if multipass is installed
    if ! command -v multipass &> /dev/null; then
        echo "Multipass not installed. Install with: sudo snap install multipass"
        exit 1
    fi
    
    # Launch Ubuntu Core VM
    multipass launch \
        --name "$VM_NAME" \
        --cpus "$VM_CPUS" \
        --memory "$VM_MEMORY" \
        --disk "$VM_DISK_SIZE" \
        "file://$(pwd)/ubuntu-core-24-amd64.img"
    
    echo "VM created. Access with: multipass shell $VM_NAME"
}

# Option 3: Using VirtualBox
setup_virtualbox_vm() {
    echo ""
    echo "=== Setting up VirtualBox VM ==="
    
    # Check if VirtualBox is installed
    if ! command -v VBoxManage &> /dev/null; then
        echo "VirtualBox not installed"
        exit 1
    fi
    
    # Convert raw image to VDI
    if [ ! -f "$VM_NAME.vdi" ]; then
        echo "Converting image to VDI format..."
        VBoxManage convertfromraw ubuntu-core-24-amd64.img "$VM_NAME.vdi" --format VDI
    fi
    
    # Create VM
    VBoxManage createvm --name "$VM_NAME" --ostype "Ubuntu_64" --register
    
    # Configure VM
    VBoxManage modifyvm "$VM_NAME" \
        --memory "$VM_MEMORY" \
        --cpus "$VM_CPUS" \
        --nic1 nat \
        --natpf1 "ssh,tcp,,10022,,22" \
        --natpf1 "web,tcp,,8111,,8111" \
        --uart1 0x3F8 4 \
        --uartmode1 file "$WORK_DIR/$VM_NAME-console.log"
    
    # Add storage controller
    VBoxManage storagectl "$VM_NAME" --name "SATA" --add sata --controller IntelAhci
    
    # Attach disk
    VBoxManage storageattach "$VM_NAME" --storagectl "SATA" --port 0 --device 0 \
        --type hdd --medium "$VM_NAME.vdi"
    
    echo "VM created. Start with: VBoxManage startvm $VM_NAME --type headless"
    echo "Console output will be in: $WORK_DIR/$VM_NAME-console.log"
}

# Create cloud-init configuration for initial setup
create_cloud_init() {
    echo ""
    echo "=== Creating cloud-init configuration ==="
    
    mkdir -p cloud-init
    
    # User data for initial configuration
    cat > cloud-init/user-data << 'EOF'
#cloud-config
# Ubuntu Core 24 initial configuration

# Create default user
system_info:
  default_user:
    name: ubuntu
    lock_passwd: false
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash

# Set hostname
hostname: ubuntu-core-24-test

# Configure SSH
ssh_authorized_keys:
  - ssh-rsa YOUR_SSH_PUBLIC_KEY_HERE

# Run commands on first boot
runcmd:
  - echo "Ubuntu Core 24 Test VM" > /etc/motd
  - snap refresh
EOF
    
    # Create meta-data
    cat > cloud-init/meta-data << EOF
instance-id: ubuntu-core-test
local-hostname: ubuntu-core-24-test
EOF
    
    echo "Cloud-init configuration created in cloud-init/"
    echo "Add your SSH public key to cloud-init/user-data before first boot"
}

# Create helper scripts
create_helper_scripts() {
    echo ""
    echo "=== Creating helper scripts ==="
    
    # SSH helper
    cat > "ssh-$VM_NAME.sh" << EOF
#!/bin/bash
ssh -p 10022 ubuntu@localhost
EOF
    chmod +x "ssh-$VM_NAME.sh"
    
    # Console connection helper
    cat > "console-$VM_NAME.sh" << EOF
#!/bin/bash
echo "Connecting to VM console..."
echo "Press Ctrl-A X to exit"
socat UNIX-CONNECT:/tmp/$VM_NAME-console STDIO
EOF
    chmod +x "console-$VM_NAME.sh"
    
    # Snap installation helper
    cat > "install-snaps-$VM_NAME.sh" << EOF
#!/bin/bash
# Install snaps in the VM

SSH_CMD="ssh -p 10022 ubuntu@localhost"

echo "Installing development snaps..."

# Install useful snaps
\$SSH_CMD "sudo snap install --classic code"
\$SSH_CMD "sudo snap install htop"
\$SSH_CMD "sudo snap install --classic snapcraft"

# Install our custom snaps
if [ -f "../snaps/ai-worker/ai-worker_1.0_amd64.snap" ]; then
    echo "Copying ai-worker snap..."
    scp -P 10022 ../snaps/ai-worker/ai-worker_1.0_amd64.snap ubuntu@localhost:~/
    \$SSH_CMD "sudo snap install --dangerous ~/ai-worker_1.0_amd64.snap"
fi

echo "Snaps installed!"
EOF
    chmod +x "install-snaps-$VM_NAME.sh"
}

# Main menu
echo ""
echo "Select VM type:"
echo "1) QEMU/KVM (recommended for Linux)"
echo "2) Multipass (easy but less control)"
echo "3) VirtualBox (cross-platform)"
echo "4) Exit"
echo ""
read -p "Choice [1-4]: " choice

case $choice in
    1)
        setup_qemu_vm
        ;;
    2)
        setup_multipass_vm
        ;;
    3)
        setup_virtualbox_vm
        ;;
    4)
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Create additional files
create_cloud_init
create_helper_scripts

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Add your SSH public key to cloud-init/user-data"
echo "2. Start the VM using the appropriate command above"
echo "3. Complete Ubuntu Core first-boot configuration"
echo "4. SSH to VM: ./ssh-$VM_NAME.sh"
echo "5. Install snaps: ./install-snaps-$VM_NAME.sh"
echo ""
echo "VM files are in: $WORK_DIR"