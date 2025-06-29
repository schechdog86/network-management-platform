#!/bin/bash
set -e

# Ray Head Node Startup Script

# Create necessary directories
mkdir -p $SNAP_DATA/ray
mkdir -p $SNAP_DATA/logs
mkdir -p $SNAP_DATA/cluster
mkdir -p $SNAP_DATA/plasma

# Export cluster information for content interface
echo "ray://$RAY_HEAD_NODE_IP:$RAY_PORT" > $SNAP_DATA/cluster/address
echo "$RAY_DASHBOARD_PORT" > $SNAP_DATA/cluster/dashboard_port

# Set up Ray configuration
export RAY_ROTATION_MAX_BYTES=104857600  # 100MB log rotation
export RAY_ROTATION_BACKUP_COUNT=5
export RAY_plasma_directory=$SNAP_DATA/plasma
export RAY_raylet_plasma_directory=$SNAP_DATA/plasma
export RAY_worker_register_timeout_seconds=30

# Check if we should join an existing cluster or start a new one
if [ -f "$SNAP_DATA/cluster/head_node_ip" ]; then
    # Join existing cluster
    HEAD_NODE_IP=$(cat $SNAP_DATA/cluster/head_node_ip)
    echo "Joining existing Ray cluster at $HEAD_NODE_IP"
    exec ray start \
        --address="$HEAD_NODE_IP:$RAY_PORT" \
        --node-ip-address="$RAY_HEAD_NODE_IP" \
        --block
else
    # Start new cluster
    echo "Starting new Ray cluster head node"
    
    # Initialize cluster configuration
    if [ -f "$SNAP/bin/cluster-init" ]; then
        python3 $SNAP/bin/cluster-init
    fi
    
    # Start Ray head node
    exec ray start \
        --head \
        --node-ip-address="$RAY_HEAD_NODE_IP" \
        --port="$RAY_PORT" \
        --dashboard-port="$RAY_DASHBOARD_PORT" \
        --redis-port="$RAY_REDIS_PORT" \
        --object-manager-port="$RAY_OBJECT_MANAGER_PORT" \
        --node-manager-port="$RAY_NODE_MANAGER_PORT" \
        --num-cpus=$(nproc) \
        --num-gpus=$(nvidia-smi -L 2>/dev/null | wc -l || echo 0) \
        --include-dashboard=true \
        --dashboard-host="0.0.0.0" \
        --block \
        --log-style=record \
        --log-color=false