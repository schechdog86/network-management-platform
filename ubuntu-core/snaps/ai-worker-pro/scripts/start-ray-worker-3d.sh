#!/bin/bash
# Advanced Ray worker with 3D parallelism support

set -e

# Load configuration
source $SNAP/etc/ai-worker-pro/worker-advanced.conf

# Function to detect hardware capabilities
detect_hardware() {
    echo "=== Hardware Detection ==="
    
    # GPU detection
    GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l || echo 0)
    echo "GPUs detected: $GPU_COUNT"
    
    if [ $GPU_COUNT -gt 0 ]; then
        # Detect GPU type
        GPU_TYPE=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | awk '{print $2}')
        echo "GPU Type: $GPU_TYPE"
        
        # Check for H100/H200 specific features
        if [[ "$GPU_TYPE" == "H100" ]] || [[ "$GPU_TYPE" == "H200" ]]; then
            echo "Detected Hopper architecture GPU - enabling FP8"
            export TRANSFORMER_ENGINE_FP8=1
            export CUDA_DEVICE_MAX_CONNECTIONS=48
        fi
        
        # Set GPU memory
        GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
        echo "GPU Memory: ${GPU_MEMORY}MB"
    fi
    
    # InfiniBand detection
    if command -v ibstat &> /dev/null; then
        IB_DEVICES=$(ibstat -l 2>/dev/null | wc -l || echo 0)
        echo "InfiniBand devices: $IB_DEVICES"
        
        if [ $IB_DEVICES -gt 0 ]; then
            export NCCL_IB_DISABLE=0
            export NCCL_NET_GDR_LEVEL=5
            export NCCL_IB_QPS_PER_CONNECTION=4
            export NCCL_IB_GID_INDEX=3
        fi
    fi
    
    # CPU and memory
    CPU_COUNT=$(nproc)
    MEMORY_GB=$(($(free -b | awk '/^Mem:/{print $2}') / 1024 / 1024 / 1024))
    echo "CPUs: $CPU_COUNT, Memory: ${MEMORY_GB}GB"
}

# Function to optimize system settings
optimize_system() {
    echo "=== System Optimization ==="
    
    # NUMA optimization
    if command -v numactl &> /dev/null; then
        NUMA_NODES=$(numactl --hardware | grep "available:" | awk '{print $2}')
        echo "NUMA nodes: $NUMA_NODES"
        
        if [ $NUMA_NODES -gt 1 ]; then
            # Bind Ray to local NUMA node
            export RAY_NUMA_BIND=1
        fi
    fi
    
    # Set process priorities
    renice -n -10 $$ || true
    
    # Increase file descriptors
    ulimit -n 1048576 || true
    
    # Configure huge pages if available
    if [ -d /sys/kernel/mm/hugepages ]; then
        echo 4096 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages || true
    fi
}

# Function to setup distributed training environment
setup_distributed_env() {
    echo "=== Distributed Training Setup ==="
    
    # DeepSpeed configuration
    export DS_ACCELERATOR=cuda
    export DS_ENV_FILE=$SNAP_DATA/deepspeed_env
    
    # Create DeepSpeed hostfile
    cat > $SNAP_DATA/deepspeed_hostfile << EOF
$(hostname) slots=$GPU_COUNT
EOF
    
    # Megatron configuration
    export MEGATRON_TENSOR_MODEL_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE:-1}
    export MEGATRON_PIPELINE_MODEL_PARALLEL_SIZE=${PIPELINE_PARALLEL_SIZE:-1}
    
    # NCCL optimization
    export NCCL_DEBUG=INFO
    export NCCL_TREE_THRESHOLD=0
    export NCCL_MIN_NCHANNELS=32
    export NCCL_MAX_NCHANNELS=32
}

# Function to start Ray with advanced configuration
start_ray_worker() {
    echo "=== Starting Ray Worker (3D Parallelism) ==="
    
    # Create necessary directories
    mkdir -p $SNAP_DATA/ray
    mkdir -p $SNAP_COMMON/logs
    mkdir -p $SNAP_COMMON/models
    mkdir -p $SNAP_COMMON/checkpoints
    
    # Wait for Ray head
    while ! ping -c 1 ${RAY_HEAD_IP:-ray-head} &> /dev/null; do
        echo "Waiting for Ray head at ${RAY_HEAD_IP:-ray-head}..."
        sleep 5
    done
    
    # Calculate resources
    if [ $GPU_COUNT -gt 0 ]; then
        RAY_RESOURCES="--num-gpus=$GPU_COUNT"
        
        # Set GPU-specific memory
        if [[ "$GPU_TYPE" == "H200" ]]; then
            # H200 has 141GB HBM3e
            GPU_MEMORY_MB=144179
        elif [[ "$GPU_TYPE" == "H100" ]]; then
            # H100 has 80GB HBM3
            GPU_MEMORY_MB=81920
        else
            GPU_MEMORY_MB=$GPU_MEMORY
        fi
        
        RAY_RESOURCES="$RAY_RESOURCES --resources={\"GPU_MEMORY_MB\":$GPU_MEMORY_MB}"
    else
        RAY_RESOURCES="--num-cpus=$CPU_COUNT"
    fi
    
    # Add custom resources for scheduling
    RAY_RESOURCES="$RAY_RESOURCES --resources={\"accelerator_type\":\"$GPU_TYPE\",\"has_nvlink\":true,\"has_infiniband\":$IB_DEVICES}"
    
    # Set object store memory (30% of system RAM)
    OBJECT_STORE_MEMORY=$(($(free -b | awk '/^Mem:/{print $2}') * 3 / 10))
    
    # Ray node labels for advanced scheduling
    NODE_LABELS="--labels={\"gpu_type\":\"$GPU_TYPE\",\"numa_nodes\":\"$NUMA_NODES\",\"ib_enabled\":\"$([ $IB_DEVICES -gt 0 ] && echo true || echo false)\"}"
    
    echo "Starting Ray worker with resources: $RAY_RESOURCES"
    
    # Start Ray
    ray start \
        --address="${RAY_HEAD_IP:-ray-head}:${RAY_HEAD_PORT:-6379}" \
        --node-ip-address="$(hostname -I | awk '{print $1}')" \
        $RAY_RESOURCES \
        $NODE_LABELS \
        --object-store-memory=$OBJECT_STORE_MEMORY \
        --temp-dir=$SNAP_DATA/ray \
        --log-dir=$SNAP_COMMON/logs \
        --metrics-export-port=8080 \
        --dashboard-agent-listen-port=52365 \
        --runtime-env-agent-port=52366 \
        --min-worker-port=10000 \
        --max-worker-port=10999 \
        --block
}

# Main execution
main() {
    echo "=== AI Worker Pro Starting ==="
    echo "Version: 2.0"
    echo "Time: $(date)"
    
    # Detect and configure hardware
    detect_hardware
    
    # Optimize system settings
    optimize_system
    
    # Setup distributed training environment
    setup_distributed_env
    
    # Start Ray worker
    start_ray_worker
}

# Error handling
trap 'echo "Error occurred at line $LINENO"; exit 1' ERR

# Run main function
main