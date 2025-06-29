#!/bin/bash
# Build and test Ubuntu Core snaps locally

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SNAPS_DIR="$PROJECT_ROOT/snaps"

echo "=== Ubuntu Core Snap Build and Test Script ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Function to build a snap
build_snap() {
    local snap_dir=$1
    local snap_name=$(basename "$snap_dir")
    
    echo "Building $snap_name..."
    cd "$snap_dir"
    
    # Clean previous builds
    snapcraft clean
    
    # Build the snap
    if snapcraft; then
        echo "✓ $snap_name built successfully"
        
        # Find the built snap file
        local snap_file=$(find . -name "*.snap" -type f | head -1)
        if [ -n "$snap_file" ]; then
            echo "  Output: $snap_file"
            return 0
        fi
    else
        echo "✗ Failed to build $snap_name"
        return 1
    fi
}

# Function to test snap confinement
test_snap_confinement() {
    local snap_file=$1
    local snap_name=$(basename "$snap_file" .snap | cut -d'_' -f1)
    
    echo ""
    echo "Testing confinement for $snap_name..."
    
    # Install in devmode first
    echo "1. Installing in devmode..."
    if sudo snap install "$snap_file" --devmode --dangerous; then
        echo "✓ Devmode installation successful"
        
        # List connections
        echo ""
        echo "2. Checking interfaces..."
        snap connections "$snap_name"
        
        # Test basic functionality
        echo ""
        echo "3. Testing basic functionality..."
        
        case "$snap_name" in
            "ai-worker"|"ai-worker-pro"|"ai-worker-budget")
                # Test AI worker commands
                if command -v "$snap_name.ai-ctl" &> /dev/null; then
                    echo "Testing ai-ctl command..."
                    "$snap_name.ai-ctl" --help || true
                fi
                ;;
            "ai-hardware-gadget")
                echo "Gadget snap - no runtime tests"
                ;;
        esac
        
        # Remove devmode installation
        sudo snap remove "$snap_name"
        
        # Try strict confinement
        echo ""
        echo "4. Testing strict confinement..."
        if sudo snap install "$snap_file" --dangerous; then
            echo "✓ Strict mode installation successful"
            
            # Test with strict confinement
            echo "Testing functionality in strict mode..."
            
            # Check if interfaces need connection
            local needs_connection=false
            local interfaces=$(snap connections "$snap_name" | grep -E "^$snap_name:" | grep -v ":network " | grep disconnected || true)
            
            if [ -n "$interfaces" ]; then
                echo "Connecting required interfaces..."
                
                # Auto-connect common interfaces
                for interface in hardware-observe system-observe mount-observe process-control; do
                    if snap connections "$snap_name" | grep -q ":$interface .*disconnected"; then
                        sudo snap connect "$snap_name:$interface"
                        echo "✓ Connected $interface"
                    fi
                done
            fi
            
            # Final test
            echo ""
            echo "5. Final functionality test..."
            case "$snap_name" in
                "ai-worker"|"ai-worker-pro"|"ai-worker-budget")
                    # Check if services are running
                    if snap services "$snap_name" 2>/dev/null | grep -q "$snap_name"; then
                        snap services "$snap_name"
                    fi
                    ;;
            esac
            
            echo "✓ Confinement test completed"
            
        else
            echo "✗ Failed to install in strict mode"
            echo "  This might indicate confinement issues"
        fi
        
    else:
        echo "✗ Failed to install in devmode"
        return 1
    fi
}

# Function to validate snap
validate_snap() {
    local snap_file=$1
    
    echo ""
    echo "Validating $snap_file..."
    
    # Use snap review if available
    if command -v snap-review &> /dev/null; then
        snap-review "$snap_file" || true
    fi
    
    # Check snap info
    snap info --verbose "$snap_file"
}

# Main execution
echo "Available snaps to build:"
echo ""

# List available snaps
snaps=($(find "$SNAPS_DIR" -name "snapcraft.yaml" -type f | xargs -I {} dirname {} | sort))

for i in "${!snaps[@]}"; do
    echo "$((i+1)). $(basename "${snaps[$i]}")"
done

echo ""
echo "Select snaps to build (comma-separated numbers, or 'all'):"
read -r selection

# Build selected snaps
if [ "$selection" = "all" ]; then
    selected_snaps=("${snaps[@]}")
else
    selected_snaps=()
    IFS=',' read -ra SELECTIONS <<< "$selection"
    for sel in "${SELECTIONS[@]}"; do
        index=$((sel-1))
        if [ $index -ge 0 ] && [ $index -lt ${#snaps[@]} ]; then
            selected_snaps+=("${snaps[$index]}")
        fi
    done
fi

# Build and test each selected snap
echo ""
echo "Building ${#selected_snaps[@]} snap(s)..."
echo ""

for snap_dir in "${selected_snaps[@]}"; do
    echo "===================================="
    echo "Processing $(basename "$snap_dir")"
    echo "===================================="
    
    if build_snap "$snap_dir"; then
        # Find the built snap
        snap_file=$(find "$snap_dir" -name "*.snap" -type f | head -1)
        
        if [ -n "$snap_file" ]; then
            # Validate
            validate_snap "$snap_file"
            
            # Test confinement
            echo ""
            read -p "Test confinement for $(basename "$snap_file")? [y/N] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                test_snap_confinement "$snap_file"
            fi
        fi
    fi
    
    echo ""
done

# Summary
echo "===================================="
echo "Build Summary"
echo "===================================="

for snap_dir in "${selected_snaps[@]}"; do
    snap_name=$(basename "$snap_dir")
    snap_file=$(find "$snap_dir" -name "*.snap" -type f | head -1)
    
    if [ -n "$snap_file" ]; then
        echo "✓ $snap_name: $(realpath "$snap_file")"
    else
        echo "✗ $snap_name: Build failed"
    fi
done

echo ""
echo "Next steps:"
echo "1. Deploy snaps to Ubuntu Core test VM"
echo "2. Test on actual hardware"
echo "3. Upload to Snap Store (when ready)"

# Create deployment helper
cat > "$PROJECT_ROOT/deploy-to-vm.sh" << 'EOF'
#!/bin/bash
# Deploy snaps to Ubuntu Core VM

VM_HOST="${1:-localhost}"
VM_PORT="${2:-10022}"

echo "Deploying snaps to $VM_HOST:$VM_PORT..."

for snap in snaps/*/*.snap; do
    if [ -f "$snap" ]; then
        echo "Copying $(basename "$snap")..."
        scp -P "$VM_PORT" "$snap" ubuntu@"$VM_HOST":~/
        
        echo "Installing $(basename "$snap")..."
        ssh -p "$VM_PORT" ubuntu@"$VM_HOST" \
            "sudo snap install --dangerous ~/$(basename "$snap")"
    fi
done

echo "Deployment complete!"
EOF

chmod +x "$PROJECT_ROOT/deploy-to-vm.sh"

echo ""
echo "Created deploy-to-vm.sh for easy deployment"