#!/bin/bash
set -e

# Ray Dashboard Startup Script

# Wait for Ray head to be ready
echo "Waiting for Ray head node..."
for i in {1..30}; do
    if ray status &>/dev/null; then
        echo "Ray head node is ready!"
        break
    fi
    echo "Waiting for Ray head... ($i/30)"
    sleep 2
done

# The dashboard is automatically started with the head node
# This script monitors its health and restarts if needed

while true; do
    # Check if dashboard is accessible
    if ! curl -s http://localhost:$RAY_DASHBOARD_PORT/api/cluster_status > /dev/null; then
        echo "Dashboard not responding, checking Ray status..."
        ray status || {
            echo "Ray cluster not healthy, restarting..."
            snapctl restart ray-head.ray-head
        }
    fi
    
    sleep 30
done