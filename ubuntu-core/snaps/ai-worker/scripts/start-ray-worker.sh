#!/bin/bash
# Start Ray worker with hardware monitoring

set -e

# Source configuration
CONFIG_FILE="${SNAP_DATA}/ray-worker.conf"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Default values
RAY_HEAD_ADDRESS="${RAY_HEAD_ADDRESS:-auto}"
RAY_WORKER_CPU_CORES="${RAY_WORKER_CPU_CORES:-}"
RAY_WORKER_GPU_NUM="${RAY_WORKER_GPU_NUM:-}"
MANAGEMENT_SERVER_URL="${MANAGEMENT_SERVER_URL:-http://localhost:8000}"
NODE_ID="${NODE_ID:-$(hostname)}"

# Log startup
echo "Starting Ray worker node..."
echo "Ray head address: $RAY_HEAD_ADDRESS"
echo "Management server: $MANAGEMENT_SERVER_URL"
echo "Node ID: $NODE_ID"

# Check for GPU support
GPU_ARGS=""
if command -v nvidia-smi &> /dev/null; then
    GPU_COUNT=$(nvidia-smi --query-gpu=count --format=csv,noheader | head -n1)
    if [ -n "$GPU_COUNT" ] && [ "$GPU_COUNT" -gt 0 ]; then
        echo "Detected $GPU_COUNT GPU(s)"
        GPU_ARGS="--num-gpus=${RAY_WORKER_GPU_NUM:-$GPU_COUNT}"
    fi
fi

# CPU cores argument
CPU_ARGS=""
if [ -n "$RAY_WORKER_CPU_CORES" ]; then
    CPU_ARGS="--num-cpus=$RAY_WORKER_CPU_CORES"
fi

# Start metrics reporter in background
export MANAGEMENT_SERVER_URL
export NODE_ID
python3 ${SNAP}/lib/ai-worker/metrics_reporter.py &
METRICS_PID=$!
echo "Started metrics reporter (PID: $METRICS_PID)"

# Function to cleanup on exit
cleanup() {
    echo "Stopping services..."
    if [ -n "$METRICS_PID" ] && kill -0 $METRICS_PID 2>/dev/null; then
        kill $METRICS_PID
    fi
    ray stop --force
    exit 0
}

trap cleanup EXIT INT TERM

# Start Ray worker
echo "Starting Ray worker..."
ray start \
    --address="$RAY_HEAD_ADDRESS" \
    --block \
    $CPU_ARGS \
    $GPU_ARGS \
    --labels='{"node_type":"ai-worker","node_id":"'$NODE_ID'"}'