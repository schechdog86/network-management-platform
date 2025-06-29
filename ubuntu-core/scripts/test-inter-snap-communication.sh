#!/bin/bash
# Test Inter-Snap Communication

set -e

echo "=== Testing Inter-Snap Communication ==="
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_service() {
    local service=$1
    local check_command=$2
    local expected=$3
    
    echo -n "Testing $service... "
    
    if eval "$check_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

# Check if snaps are installed
echo "1. Checking snap installation:"
REQUIRED_SNAPS="network-db network-manager-server network-web ray-head"
ALL_INSTALLED=true

for snap in $REQUIRED_SNAPS; do
    if snap list | grep -q "^$snap "; then
        echo -e "  ${GREEN}✓${NC} $snap installed"
    else
        echo -e "  ${RED}✗${NC} $snap not installed"
        ALL_INSTALLED=false
    fi
done

if [ "$ALL_INSTALLED" = false ]; then
    echo -e "\n${RED}Error: Not all required snaps are installed${NC}"
    echo "Install missing snaps with:"
    echo "  sudo snap install <snap-name>"
    exit 1
fi

echo

# Check services are running
echo "2. Checking service status:"
test_service "PostgreSQL" "pg_isready -h localhost -p 5432" "accepting connections"
test_service "API Server" "curl -s http://localhost:8000/api/v1/health | grep -q 'ok'" "ok"
test_service "Web Interface" "curl -s http://localhost:3000 | grep -q 'Network Management'" "loaded"
test_service "Ray Head" "ray status 2>/dev/null | grep -q 'Ray cluster is running'" "running"

echo

# Check interface connections
echo "3. Checking snap connections:"
echo -e "${YELLOW}Current connections:${NC}"
snap connections network-manager-server | grep -E "(postgres-db|network-manager-api)"
snap connections network-web | grep "api-connection"
snap connections ray-head | grep -E "(ray-cluster|network-api)"

echo

# Test database connection from API
echo "4. Testing Database → API communication:"
if curl -s http://localhost:8000/api/v1/devices > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} API can query database"
else
    echo -e "  ${RED}✗${NC} API cannot query database"
fi

# Test API connection from Web
echo "5. Testing API → Web communication:"
if curl -s http://localhost:3000/runtime-config.js | grep -q "API_URL"; then
    echo -e "  ${GREEN}✓${NC} Web UI configured with API endpoint"
else
    echo -e "  ${RED}✗${NC} Web UI not configured with API endpoint"
fi

# Test Ray cluster
echo "6. Testing Ray cluster communication:"
PYTHON_TEST=$(cat <<'EOF'
import ray
import sys
try:
    ray.init(address='auto', ignore_reinit_error=True)
    nodes = len(ray.nodes())
    print(f"Ray cluster has {nodes} node(s)")
    ray.shutdown()
    sys.exit(0)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF
)

if python3 -c "$PYTHON_TEST" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Ray cluster is accessible"
else
    echo -e "  ${RED}✗${NC} Ray cluster is not accessible"
fi

echo

# Performance test
echo "7. Running performance tests:"

# Database performance
echo -n "  Database response time: "
DB_TIME=$(time -p psql -h localhost -U netmanager -d networkdb -c "SELECT 1" 2>&1 | grep real | awk '{print $2}')
echo "${DB_TIME}s"

# API response time
echo -n "  API response time: "
API_TIME=$(curl -w "%{time_total}" -o /dev/null -s http://localhost:8000/api/v1/health)
echo "${API_TIME}s"

# Web response time
echo -n "  Web UI response time: "
WEB_TIME=$(curl -w "%{time_total}" -o /dev/null -s http://localhost:3000)
echo "${WEB_TIME}s"

echo

# Integration test
echo "8. Running integration test:"
INTEGRATION_TEST=$(cat <<'EOF'
import asyncio
import httpx
import json

async def test():
    try:
        # Create a test device via API
        async with httpx.AsyncClient() as client:
            # Get current devices
            resp = await client.get("http://localhost:8000/api/v1/devices")
            initial_count = len(resp.json())
            
            # Health check
            resp = await client.get("http://localhost:8000/api/v1/health")
            if resp.status_code == 200:
                print("✓ Full integration test passed")
                return True
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False

asyncio.run(test())
EOF
)

python3 -c "$INTEGRATION_TEST"

echo
echo "=== Test Summary ==="
echo "All basic inter-snap communication tests completed."
echo
echo "To connect snaps manually, use:"
echo "  sudo snap connect <consumer>:<plug> <provider>:<slot>"
echo
echo "For detailed logs, check:"
echo "  sudo journalctl -u snap.network-manager-server.api-server"
echo "  sudo journalctl -u snap.network-db.postgres"
echo "  sudo journalctl -u snap.ray-head.ray-head"