#!/usr/bin/env python3
"""PyTorch worker service for distributed training"""

import os
import sys
import time
import json
import torch
import torch.distributed as dist
from datetime import datetime
import psutil
import socket

class PyTorchWorker:
    def __init__(self):
        self.hostname = socket.gethostname()
        self.snap_common = os.environ.get('SNAP_COMMON', '.')
        self.model_cache = os.path.join(self.snap_common, 'models')
        
        # Ensure model cache directory exists
        os.makedirs(self.model_cache, exist_ok=True)
        
        # Set PyTorch cache directory
        os.environ['TORCH_HOME'] = os.path.join(self.model_cache, 'torch')
        
        # Initialize GPU if available
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
        
        print(f"PyTorch Worker initialized on {self.hostname}")
        print(f"Device: {self.device}")
        print(f"GPU count: {self.gpu_count}")
        
        if self.gpu_count > 0:
            for i in range(self.gpu_count):
                print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
                print(f"  Memory: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.1f} GB")
    
    def setup_distributed(self):
        """Setup distributed training if environment variables are set"""
        if 'MASTER_ADDR' in os.environ and 'MASTER_PORT' in os.environ:
            rank = int(os.environ.get('RANK', 0))
            world_size = int(os.environ.get('WORLD_SIZE', 1))
            
            print(f"Initializing distributed training: rank={rank}, world_size={world_size}")
            
            # Initialize the process group
            dist.init_process_group(
                backend='nccl' if torch.cuda.is_available() else 'gloo',
                rank=rank,
                world_size=world_size
            )
            
            if torch.cuda.is_available():
                # Set the GPU for this process
                local_rank = int(os.environ.get('LOCAL_RANK', 0))
                torch.cuda.set_device(local_rank)
                
            return True
        return False
    
    def monitor_resources(self):
        """Monitor system resources"""
        stats = {
            'timestamp': datetime.utcnow().isoformat(),
            'hostname': self.hostname,
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'gpu_stats': []
        }
        
        if torch.cuda.is_available():
            for i in range(self.gpu_count):
                allocated = torch.cuda.memory_allocated(i)
                reserved = torch.cuda.memory_reserved(i)
                total = torch.cuda.get_device_properties(i).total_memory
                
                stats['gpu_stats'].append({
                    'index': i,
                    'allocated_mb': allocated / 1024**2,
                    'reserved_mb': reserved / 1024**2,
                    'total_mb': total / 1024**2,
                    'utilization': (allocated / total) * 100
                })
        
        return stats
    
    def handle_training_request(self, request):
        """Handle incoming training requests"""
        # This would be implemented based on your specific training needs
        # For now, it's a placeholder that shows the structure
        
        model_name = request.get('model')
        dataset = request.get('dataset')
        config = request.get('config', {})
        
        print(f"Received training request: model={model_name}, dataset={dataset}")
        
        # Example: Load a pre-trained model
        if model_name == 'resnet50':
            from torchvision import models
            model = models.resnet50(pretrained=True)
            model = model.to(self.device)
            
            if self.gpu_count > 1:
                model = torch.nn.DataParallel(model)
            
            print("Model loaded successfully")
            return {'status': 'success', 'message': 'Model loaded'}
        
        return {'status': 'error', 'message': f'Unknown model: {model_name}'}
    
    def run(self):
        """Main worker loop"""
        print("PyTorch worker started")
        
        # Setup distributed training if configured
        is_distributed = self.setup_distributed()
        
        # Main loop
        while True:
            try:
                # Monitor resources
                stats = self.monitor_resources()
                
                # Log stats
                stats_file = os.path.join(self.snap_common, 'pytorch-stats.json')
                with open(stats_file, 'w') as f:
                    json.dump(stats, f, indent=2)
                
                # In a real implementation, you would:
                # 1. Listen for training requests (via Ray, gRPC, or REST API)
                # 2. Process training jobs
                # 3. Report results back
                
                # For now, just log status
                if is_distributed:
                    rank = dist.get_rank()
                    world_size = dist.get_world_size()
                    print(f"[Rank {rank}/{world_size}] Worker active, GPU memory: {stats['gpu_stats']}")
                else:
                    print(f"Worker active, GPU memory: {stats['gpu_stats']}")
                
            except Exception as e:
                print(f"Error in worker loop: {e}")
            
            time.sleep(30)

if __name__ == '__main__':
    worker = PyTorchWorker()
    worker.run()