#!/bin/bash
set -e

# Load configuration
source $SNAP/etc/ai-worker/worker.conf

# Wait for network
while ! ping -c 1 ${RAY_HEAD_IP:-ray-head} &> /dev/null; do
    echo "Waiting for network connectivity..."
    sleep 5
done

# Detect GPU capabilities
GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l || echo 0)
echo "Detected $GPU_COUNT GPUs"

# Set Ray resources based on hardware
if [ $GPU_COUNT -gt 0 ]; then
    RAY_RESOURCES="--num-gpus=$GPU_COUNT"
else
    RAY_RESOURCES="--num-cpus=$(nproc)"
fi

# Create necessary directories
mkdir -p $SNAP_DATA/ray
mkdir -p $SNAP_COMMON/logs
mkdir -p $SNAP_COMMON/models

# Start Ray worker
echo "Starting Ray worker node..."
echo "Connecting to Ray head at ${RAY_HEAD_IP:-ray-head}:6379"

ray start \
    --address="${RAY_HEAD_IP:-ray-head}:6379" \
    --node-ip-address="$(hostname -I | awk '{print $1}')" \
    $RAY_RESOURCES \
    --object-store-memory=$(($(free -b | awk '/^Mem:/{print $2}') * 3 / 10)) \
    --temp-dir=$SNAP_DATA/ray \
    --log-dir=$SNAP_COMMON/logs \
    --metrics-export-port=8080 \
    --dashboard-agent-listen-port=52365 \
    --block