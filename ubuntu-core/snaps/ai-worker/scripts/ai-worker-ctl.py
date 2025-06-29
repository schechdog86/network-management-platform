#!/usr/bin/env python3
"""Command-line tool for managing AI worker node"""

import argparse
import json
import os
import sys
import subprocess
import psutil

try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False

try:
    import nvidia_ml_py as nvml
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False

class AIWorkerControl:
    def __init__(self):
        self.snap_data = os.environ.get('SNAP_DATA', '.')
        self.snap_common = os.environ.get('SNAP_COMMON', '.')
        
    def status(self):
        """Show worker status"""
        print("=== AI Worker Status ===")
        
        # System info
        print(f"\nSystem:")
        print(f"  Hostname: {os.uname().nodename}")
        print(f"  CPUs: {psutil.cpu_count()}")
        print(f"  Memory: {psutil.virtual_memory().total / 1024**3:.1f} GB")
        print(f"  CPU Usage: {psutil.cpu_percent(interval=1)}%")
        print(f"  Memory Usage: {psutil.virtual_memory().percent}%")
        
        # GPU info
        if NVIDIA_AVAILABLE:
            try:
                nvml.nvmlInit()
                gpu_count = nvml.nvmlDeviceGetCount()
                print(f"\nGPUs: {gpu_count} detected")
                for i in range(gpu_count):
                    handle = nvml.nvmlDeviceGetHandleByIndex(i)
                    name = nvml.nvmlDeviceGetName(handle).decode('utf-8')
                    memory = nvml.nvmlDeviceGetMemoryInfo(handle)
                    util = nvml.nvmlDeviceGetUtilizationRates(handle)
                    temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                    
                    print(f"  GPU {i}: {name}")
                    print(f"    Memory: {memory.used/1024**3:.1f}/{memory.total/1024**3:.1f} GB")
                    print(f"    Utilization: {util.gpu}%")
                    print(f"    Temperature: {temp}°C")
            except Exception as e:
                print(f"\nGPUs: Error - {e}")
        else:
            print("\nGPUs: nvidia-ml-py not available")
        
        # Ray status
        print("\nRay Status:")
        if RAY_AVAILABLE:
            try:
                ray.init(address='auto', ignore_reinit_error=True)
                print("  Connected to Ray cluster")
                resources = ray.cluster_resources()
                print(f"  Cluster CPUs: {resources.get('CPU', 0)}")
                print(f"  Cluster GPUs: {resources.get('GPU', 0)}")
                print(f"  Cluster Memory: {resources.get('memory', 0) / 1024**3:.1f} GB")
            except Exception as e:
                print(f"  Not connected: {e}")
        else:
            print("  Ray not installed")
        
        # Service status
        print("\nServices:")
        services = ['ray-worker', 'pytorch-worker', 'tf-serving', 'monitor']
        for service in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', f'snap.ai-worker.{service}'],
                    capture_output=True, text=True
                )
                status = result.stdout.strip()
                print(f"  {service}: {status}")
            except:
                print(f"  {service}: unknown")
    
    def logs(self, service='ray-worker', lines=50):
        """Show service logs"""
        print(f"=== Logs for {service} (last {lines} lines) ===")
        try:
            subprocess.run([
                'journalctl', '-u', f'snap.ai-worker.{service}',
                '-n', str(lines), '--no-pager'
            ])
        except Exception as e:
            print(f"Error reading logs: {e}")
    
    def restart(self, service='ray-worker'):
        """Restart a service"""
        print(f"Restarting {service}...")
        try:
            subprocess.run([
                'systemctl', 'restart', f'snap.ai-worker.{service}'
            ], check=True)
            print(f"✓ {service} restarted")
        except Exception as e:
            print(f"✗ Error restarting {service}: {e}")
    
    def test_gpu(self):
        """Test GPU functionality"""
        print("=== GPU Test ===")
        
        # Test PyTorch
        print("\nTesting PyTorch...")
        try:
            import torch
            print(f"PyTorch version: {torch.__version__}")
            print(f"CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                print(f"CUDA version: {torch.version.cuda}")
                print(f"GPU count: {torch.cuda.device_count()}")
                for i in range(torch.cuda.device_count()):
                    print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
                
                # Simple computation test
                print("\nRunning GPU computation test...")
                x = torch.randn(1000, 1000).cuda()
                y = torch.randn(1000, 1000).cuda()
                z = torch.matmul(x, y)
                print("✓ PyTorch GPU computation successful")
        except Exception as e:
            print(f"✗ PyTorch test failed: {e}")
        
        # Test TensorFlow
        print("\nTesting TensorFlow...")
        try:
            import tensorflow as tf
            print(f"TensorFlow version: {tf.__version__}")
            gpus = tf.config.list_physical_devices('GPU')
            print(f"GPU count: {len(gpus)}")
            for gpu in gpus:
                print(f"  {gpu}")
            
            if gpus:
                # Simple computation test
                print("\nRunning TF GPU computation test...")
                with tf.device('/GPU:0'):
                    a = tf.constant([[1.0, 2.0], [3.0, 4.0]])
                    b = tf.constant([[1.0, 1.0], [0.0, 1.0]])
                    c = tf.matmul(a, b)
                print("✓ TensorFlow GPU computation successful")
        except Exception as e:
            print(f"✗ TensorFlow test failed: {e}")
    
    def cache_info(self):
        """Show model cache information"""
        print("=== Model Cache Info ===")
        cache_dir = os.path.join(self.snap_common, 'models')
        
        if os.path.exists(cache_dir):
            total_size = 0
            model_count = 0
            
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    model_count += 1
            
            print(f"Cache directory: {cache_dir}")
            print(f"Total models: {model_count}")
            print(f"Total size: {total_size / 1024**3:.2f} GB")
            
            # List models
            print("\nCached models:")
            for root, dirs, files in os.walk(cache_dir):
                level = root.replace(cache_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 2 * (level + 1)
                for file in files[:10]:  # Limit to first 10 files
                    size = os.path.getsize(os.path.join(root, file))
                    print(f"{subindent}{file} ({size / 1024**2:.1f} MB)")
                if len(files) > 10:
                    print(f"{subindent}... and {len(files) - 10} more files")
        else:
            print(f"Cache directory not found: {cache_dir}")

def main():
    parser = argparse.ArgumentParser(description='AI Worker Control Tool')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Status command
    subparsers.add_parser('status', help='Show worker status')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('service', nargs='?', default='ray-worker',
                           choices=['ray-worker', 'pytorch-worker', 'tf-serving', 'monitor'],
                           help='Service to show logs for')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of lines to show')
    
    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart a service')
    restart_parser.add_argument('service', nargs='?', default='ray-worker',
                              choices=['ray-worker', 'pytorch-worker', 'tf-serving', 'monitor'],
                              help='Service to restart')
    
    # Test GPU command
    subparsers.add_parser('test-gpu', help='Test GPU functionality')
    
    # Cache info command
    subparsers.add_parser('cache-info', help='Show model cache information')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    controller = AIWorkerControl()
    
    if args.command == 'status':
        controller.status()
    elif args.command == 'logs':
        controller.logs(args.service, args.lines)
    elif args.command == 'restart':
        controller.restart(args.service)
    elif args.command == 'test-gpu':
        controller.test_gpu()
    elif args.command == 'cache-info':
        controller.cache_info()

if __name__ == '__main__':
    main()