#!/bin/bash

# Start Ray Head Node for Network Management Platform
set -e

echo "Starting Ray Head Node..."

# Wait for GPU availability
while ! nvidia-smi > /dev/null 2>&1; do
    echo "Waiting for GPU availability..."
    sleep 5
done

echo "GPUs detected:"
nvidia-smi --list-gpus

# Start Ray head node with GPU support
ray start \
    --head \
    --dashboard-host=0.0.0.0 \
    --dashboard-port=8265 \
    --port=10001 \
    --metrics-export-port=8080 \
    --object-manager-port=8077 \
    --node-manager-port=8076 \
    --resources='{"CPU":16,"GPU":4,"memory":64000000000,"NetworkScanner":4,"BackupProcessor":4,"AIInference":4}' \
    --temp-dir=/tmp/ray

echo "Ray head node started successfully"
echo "Dashboard available at: http://0.0.0.0:8265"
echo "Ray client address: ray://0.0.0.0:10001"

# Keep the container running
tail -f /tmp/ray/session_latest/logs/dashboard.log