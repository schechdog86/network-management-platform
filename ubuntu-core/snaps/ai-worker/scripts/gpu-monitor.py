#!/usr/bin/env python3
"""GPU monitoring service for AI worker nodes"""

import time
import json
import psutil
import socket
import os
from datetime import datetime

try:
    import nvidia_ml_py as nvml
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False

class GPUMonitor:
    def __init__(self):
        if NVIDIA_AVAILABLE:
            try:
                nvml.nvmlInit()
                self.gpu_count = nvml.nvmlDeviceGetCount()
            except:
                self.gpu_count = 0
                NVIDIA_AVAILABLE = False
        else:
            self.gpu_count = 0
        
        self.hostname = socket.gethostname()
        self.snap_data = os.environ.get('SNAP_DATA', '.')
        
    def get_gpu_stats(self):
        """Collect GPU statistics"""
        stats = []
        
        if not NVIDIA_AVAILABLE or self.gpu_count == 0:
            return stats
            
        for i in range(self.gpu_count):
            try:
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                
                # Get GPU information
                name = nvml.nvmlDeviceGetName(handle).decode('utf-8')
                memory = nvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
                temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to watts
                
                # Get running processes
                processes = []
                try:
                    procs = nvml.nvmlDeviceGetComputeRunningProcesses(handle)
                    for p in procs:
                        processes.append({
                            'pid': p.pid,
                            'memory_mb': p.usedGpuMemory / 1024 / 1024
                        })
                except:
                    pass
                
                stats.append({
                    'index': i,
                    'name': name,
                    'memory_used': memory.used,
                    'memory_total': memory.total,
                    'memory_percent': (memory.used / memory.total) * 100,
                    'gpu_utilization': utilization.gpu,
                    'memory_utilization': utilization.memory,
                    'temperature': temperature,
                    'power_watts': power,
                    'processes': processes
                })
            except Exception as e:
                print(f"Error reading GPU {i}: {e}")
                
        return stats
    
    def get_system_stats(self):
        """Collect system statistics"""
        # Get network stats
        net_io = psutil.net_io_counters()
        
        # Get disk I/O stats
        disk_io = psutil.disk_io_counters()
        
        return {
            'hostname': self.hostname,
            'timestamp': datetime.utcnow().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'cpu_count': psutil.cpu_count(),
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent,
                'used': psutil.virtual_memory().used
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'percent': psutil.disk_usage('/').percent
            },
            'network': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            },
            'disk_io': {
                'read_bytes': disk_io.read_bytes,
                'write_bytes': disk_io.write_bytes,
                'read_count': disk_io.read_count,
                'write_count': disk_io.write_count
            }
        }
    
    def check_ray_status(self):
        """Check if Ray is running and connected"""
        try:
            import ray
            if ray.is_initialized():
                return {
                    'connected': True,
                    'address': ray.get_runtime_context().address_info
                }
        except:
            pass
        return {'connected': False}
    
    def run(self):
        """Main monitoring loop"""
        print(f"Starting GPU monitor on {self.hostname}")
        print(f"Detected {self.gpu_count} GPUs")
        
        while True:
            try:
                stats = {
                    'system': self.get_system_stats(),
                    'gpus': self.get_gpu_stats(),
                    'ray': self.check_ray_status()
                }
                
                # Write to log file
                stats_file = os.path.join(self.snap_data, 'gpu-stats.json')
                with open(stats_file, 'w') as f:
                    json.dump(stats, f, indent=2)
                
                # Also write a summary to stdout for journald
                summary = {
                    'timestamp': stats['system']['timestamp'],
                    'hostname': self.hostname,
                    'cpu_percent': stats['system']['cpu_percent'],
                    'memory_percent': stats['system']['memory']['percent'],
                    'gpu_count': len(stats['gpus'])
                }
                
                if stats['gpus']:
                    gpu_utils = [gpu['gpu_utilization'] for gpu in stats['gpus']]
                    summary['avg_gpu_utilization'] = sum(gpu_utils) / len(gpu_utils)
                    summary['max_gpu_temp'] = max(gpu['temperature'] for gpu in stats['gpus'])
                
                print(json.dumps(summary))
                
            except Exception as e:
                print(f"Error collecting stats: {e}")
                
            time.sleep(30)  # Collect stats every 30 seconds

if __name__ == '__main__':
    monitor = GPUMonitor()
    monitor.run()