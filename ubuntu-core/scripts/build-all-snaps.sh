#!/bin/bash
# Build all Network Management Platform snaps

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SNAPS_DIR="$PROJECT_ROOT/snaps"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=== Building All Network Management Platform Snaps ==="
echo

# List of snaps to build in order
SNAPS=(
    "network-db"
    "network-manager-server"
    "network-web"
    "ray-head"
    "ai-worker"
    "ai-worker-pro"
    "ai-worker-budget"
)

# Check snapcraft is installed
if ! command -v snapcraft &> /dev/null; then
    echo -e "${RED}Error: snapcraft is not installed${NC}"
    echo "Install with: sudo snap install snapcraft --classic"
    exit 1
fi

# Create output directory
OUTPUT_DIR="$PROJECT_ROOT/build/snaps"
mkdir -p "$OUTPUT_DIR"

# Build each snap
FAILED_SNAPS=()

for snap in "${SNAPS[@]}"; do
    SNAP_DIR="$SNAPS_DIR/$snap"
    
    if [ ! -d "$SNAP_DIR" ]; then
        echo -e "${YELLOW}Warning: Snap directory not found: $SNAP_DIR${NC}"
        continue
    fi
    
    echo -e "\n${GREEN}Building $snap...${NC}"
    echo "Directory: $SNAP_DIR"
    
    cd "$SNAP_DIR"
    
    # Clean previous builds
    if [ -d "parts" ] || [ -d "stage" ] || [ -d "prime" ]; then
        echo "Cleaning previous build artifacts..."
        snapcraft clean
    fi
    
    # Build the snap
    if snapcraft 2>&1 | tee "$OUTPUT_DIR/${snap}-build.log"; then
        # Move built snap to output directory
        if ls *.snap 1> /dev/null 2>&1; then
            mv *.snap "$OUTPUT_DIR/"
            echo -e "${GREEN}✓ Successfully built $snap${NC}"
        else
            echo -e "${RED}✗ No snap file found for $snap${NC}"
            FAILED_SNAPS+=("$snap")
        fi
    else
        echo -e "${RED}✗ Failed to build $snap${NC}"
        FAILED_SNAPS+=("$snap")
    fi
done

echo -e "\n=== Build Summary ==="
echo "Output directory: $OUTPUT_DIR"
echo

# List built snaps
echo "Successfully built snaps:"
ls -la "$OUTPUT_DIR"/*.snap 2>/dev/null || echo "  None"

# Report failures
if [ ${#FAILED_SNAPS[@]} -gt 0 ]; then
    echo -e "\n${RED}Failed snaps:${NC}"
    for snap in "${FAILED_SNAPS[@]}"; do
        echo "  - $snap (see $OUTPUT_DIR/${snap}-build.log)"
    done
    exit 1
else
    echo -e "\n${GREEN}All snaps built successfully!${NC}"
fi

# Installation instructions
echo -e "\n=== Installation Instructions ==="
echo "To install the snaps locally:"
echo
echo "# Install in order (respecting dependencies)"
echo "sudo snap install --dangerous $OUTPUT_DIR/network-db_*.snap"
echo "sudo snap install --dangerous $OUTPUT_DIR/network-manager-server_*.snap"
echo "sudo snap install --dangerous $OUTPUT_DIR/network-web_*.snap"
echo "sudo snap install --dangerous $OUTPUT_DIR/ray-head_*.snap"
echo "sudo snap install --dangerous $OUTPUT_DIR/ai-worker_*.snap"
echo
echo "# Connect interfaces"
echo "sudo snap connect network-manager-server:postgres-db network-db:postgres-socket"
echo "sudo snap connect network-web:api-connection network-manager-server:network-manager-api"
echo "sudo snap connect ray-head:network-api network-manager-server:network-manager-api"
echo "sudo snap connect ai-worker:ray-cluster ray-head:ray-cluster"
echo
echo "# Test the installation"
echo "$SCRIPT_DIR/test-inter-snap-communication.sh"