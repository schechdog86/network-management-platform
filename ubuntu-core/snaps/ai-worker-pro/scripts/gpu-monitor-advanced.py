#!/usr/bin/env python3
"""Advanced GPU monitoring with H100/H200 specific metrics"""

import os
import sys
import time
import json
import psutil
import socket
import subprocess
from datetime import datetime
from collections import defaultdict
import threading
import queue

try:
    import pynvml
    pynvml.nvmlInit()
    NVIDIA_AVAILABLE = True
except:
    NVIDIA_AVAILABLE = False

try:
    import py3nvml.py3nvml as nvml
    nvml.nvmlInit()
    DCGM_AVAILABLE = True
except:
    DCGM_AVAILABLE = False

try:
    from prometheus_client import start_http_server, Gauge, Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except:
    PROMETHEUS_AVAILABLE = False

class AdvancedGPUMonitor:
    def __init__(self):
        self.hostname = socket.gethostname()
        self.snap_data = os.environ.get('SNAP_DATA', '.')
        self.metrics_queue = queue.Queue()
        
        # Initialize Prometheus metrics if available
        if PROMETHEUS_AVAILABLE:
            self.setup_prometheus_metrics()
            
        # Detect GPU architecture
        self.gpu_architecture = self.detect_gpu_architecture()
        print(f"Detected GPU architecture: {self.gpu_architecture}")
        
    def detect_gpu_architecture(self):
        """Detect GPU architecture (Hopper, Ampere, etc.)"""
        if not NVIDIA_AVAILABLE:
            return "unknown"
            
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                
                if 'H100' in name or 'H200' in name:
                    return 'hopper'
                elif 'A100' in name:
                    return 'ampere'
                elif 'V100' in name:
                    return 'volta'
                else:
                    return 'other'
        except:
            return "unknown"
            
    def setup_prometheus_metrics(self):
        """Setup Prometheus metrics"""
        # GPU metrics
        self.gpu_utilization = Gauge('gpu_utilization_percent', 'GPU utilization percentage', ['gpu_index', 'gpu_name'])
        self.gpu_memory_used = Gauge('gpu_memory_used_bytes', 'GPU memory used in bytes', ['gpu_index', 'gpu_name'])
        self.gpu_memory_total = Gauge('gpu_memory_total_bytes', 'GPU memory total in bytes', ['gpu_index', 'gpu_name'])
        self.gpu_temperature = Gauge('gpu_temperature_celsius', 'GPU temperature in Celsius', ['gpu_index', 'gpu_name'])
        self.gpu_power_usage = Gauge('gpu_power_usage_watts', 'GPU power usage in watts', ['gpu_index', 'gpu_name'])
        
        # H100/H200 specific metrics
        self.gpu_fp8_active = Gauge('gpu_fp8_active', 'FP8 compute active', ['gpu_index', 'gpu_name'])
        self.gpu_tensor_core_util = Gauge('gpu_tensor_core_utilization', 'Tensor core utilization', ['gpu_index', 'gpu_name'])
        self.gpu_nvlink_throughput = Gauge('gpu_nvlink_throughput_gbps', 'NVLink throughput in Gbps', ['gpu_index', 'gpu_name'])
        
        # InfiniBand metrics
        self.ib_port_data_received = Counter('infiniband_port_data_received_bytes', 'InfiniBand data received', ['port'])
        self.ib_port_data_transmitted = Counter('infiniband_port_data_transmitted_bytes', 'InfiniBand data transmitted', ['port'])
        
        # System metrics
        self.cpu_utilization = Gauge('node_cpu_utilization_percent', 'CPU utilization percentage')
        self.memory_utilization = Gauge('node_memory_utilization_percent', 'Memory utilization percentage')
        
    def get_gpu_metrics(self):
        """Get comprehensive GPU metrics including H100/H200 specific data"""
        if not NVIDIA_AVAILABLE:
            return []
            
        metrics = []
        device_count = pynvml.nvmlDeviceGetCount()
        
        for i in range(device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                
                # Basic metrics
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                
                gpu_metrics = {
                    'index': i,
                    'name': name,
                    'architecture': self.gpu_architecture,
                    'memory_used': memory.used,
                    'memory_total': memory.total,
                    'memory_free': memory.free,
                    'memory_percent': (memory.used / memory.total) * 100,
                    'gpu_utilization': utilization.gpu,
                    'memory_utilization': utilization.memory,
                    'temperature': temperature,
                    'power_watts': power,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Get additional metrics for Hopper architecture
                if self.gpu_architecture == 'hopper':
                    gpu_metrics.update(self.get_hopper_metrics(handle, i))
                
                # Get PCIe/NVLink info
                gpu_metrics.update(self.get_interconnect_metrics(handle))
                
                # Get compute capabilities
                gpu_metrics.update(self.get_compute_metrics(handle))
                
                # Update Prometheus metrics if available
                if PROMETHEUS_AVAILABLE:
                    self.update_prometheus_gpu_metrics(gpu_metrics)
                
                metrics.append(gpu_metrics)
                
            except Exception as e:
                print(f"Error reading GPU {i}: {e}")
                
        return metrics
        
    def get_hopper_metrics(self, handle, gpu_index):
        """Get H100/H200 specific metrics"""
        hopper_metrics = {}
        
        try:
            # Check if FP8 is being used (requires newer pynvml)
            if hasattr(pynvml, 'nvmlDeviceGetComputeMode'):
                compute_mode = pynvml.nvmlDeviceGetComputeMode(handle)
                hopper_metrics['compute_mode'] = compute_mode
                
            # Get memory bandwidth utilization
            if hasattr(pynvml, 'nvmlDeviceGetMemoryBusWidth'):
                bus_width = pynvml.nvmlDeviceGetMemoryBusWidth(handle)
                hopper_metrics['memory_bus_width'] = bus_width
                
            # Get multi-instance GPU (MIG) info
            if hasattr(pynvml, 'nvmlDeviceGetMigMode'):
                mig_mode = pynvml.nvmlDeviceGetMigMode(handle)
                hopper_metrics['mig_enabled'] = mig_mode[0] == 1
                
            # Estimate tensor core utilization (heuristic based on GPU and memory util)
            gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            mem_util = pynvml.nvmlDeviceGetUtilizationRates(handle).memory
            hopper_metrics['estimated_tensor_core_util'] = min(gpu_util, mem_util) * 0.8
            
        except Exception as e:
            print(f"Error getting Hopper metrics: {e}")
            
        return hopper_metrics
        
    def get_interconnect_metrics(self, handle):
        """Get PCIe and NVLink metrics"""
        interconnect_metrics = {}
        
        try:
            # PCIe throughput
            if hasattr(pynvml, 'nvmlDeviceGetPcieThroughput'):
                pcie_tx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_TX_BYTES)
                pcie_rx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_RX_BYTES)
                interconnect_metrics['pcie_tx_throughput'] = pcie_tx
                interconnect_metrics['pcie_rx_throughput'] = pcie_rx
                
            # NVLink status
            if hasattr(pynvml, 'nvmlDeviceGetNvLinkState'):
                nvlink_count = 0
                nvlink_throughput = 0
                
                for link in range(12):  # H100 has up to 12 NVLinks
                    try:
                        state = pynvml.nvmlDeviceGetNvLinkState(handle, link)
                        if state == pynvml.NVML_FEATURE_ENABLED:
                            nvlink_count += 1
                    except:
                        break
                        
                interconnect_metrics['nvlink_count'] = nvlink_count
                interconnect_metrics['nvlink_total_bandwidth_gb'] = nvlink_count * 100  # 100GB/s per link for H100
                
        except Exception as e:
            print(f"Error getting interconnect metrics: {e}")
            
        return interconnect_metrics
        
    def get_compute_metrics(self, handle):
        """Get compute capability metrics"""
        compute_metrics = {}
        
        try:
            # Get SM clock speed
            sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            compute_metrics['sm_clock_mhz'] = sm_clock
            
            # Get memory clock speed
            mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
            compute_metrics['memory_clock_mhz'] = mem_clock
            
            # Get current performance state
            pstate = pynvml.nvmlDeviceGetPerformanceState(handle)
            compute_metrics['performance_state'] = f"P{pstate}"
            
            # Get throttle reasons
            throttle_reasons = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle)
            compute_metrics['throttled'] = throttle_reasons != 0
            
            if throttle_reasons != 0:
                reasons = []
                if throttle_reasons & pynvml.nvmlClocksThrottleReasonGpuIdle:
                    reasons.append("idle")
                if throttle_reasons & pynvml.nvmlClocksThrottleReasonApplicationsClocksSetting:
                    reasons.append("applications_clocks")
                if throttle_reasons & pynvml.nvmlClocksThrottleReasonSwPowerCap:
                    reasons.append("sw_power_cap")
                if throttle_reasons & pynvml.nvmlClocksThrottleReasonHwSlowdown:
                    reasons.append("hw_slowdown")
                compute_metrics['throttle_reasons'] = reasons
                
        except Exception as e:
            print(f"Error getting compute metrics: {e}")
            
        return compute_metrics
        
    def get_infiniband_metrics(self):
        """Get InfiniBand network metrics"""
        ib_metrics = []
        
        try:
            # Check if ibstat is available
            result = subprocess.run(['ibstat', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                devices = result.stdout.strip().split('\n')
                
                for device in devices:
                    if device:
                        # Get port info
                        port_result = subprocess.run(['ibstat', device, '-s'], capture_output=True, text=True)
                        if port_result.returncode == 0:
                            # Parse counters
                            counters_result = subprocess.run(['perfquery', '-x', device], capture_output=True, text=True)
                            if counters_result.returncode == 0:
                                metrics = self.parse_ib_counters(counters_result.stdout)
                                metrics['device'] = device
                                ib_metrics.append(metrics)
                                
        except Exception as e:
            print(f"Error getting InfiniBand metrics: {e}")
            
        return ib_metrics
        
    def parse_ib_counters(self, output):
        """Parse InfiniBand performance counters"""
        metrics = {}
        
        for line in output.split('\n'):
            if 'PortXmitData' in line:
                metrics['xmit_data_gb'] = int(line.split()[-1]) / 1024 / 1024 / 1024
            elif 'PortRcvData' in line:
                metrics['rcv_data_gb'] = int(line.split()[-1]) / 1024 / 1024 / 1024
            elif 'PortXmitPkts' in line:
                metrics['xmit_packets'] = int(line.split()[-1])
            elif 'PortRcvPkts' in line:
                metrics['rcv_packets'] = int(line.split()[-1])
                
        return metrics
        
    def get_system_metrics(self):
        """Get system-level metrics"""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        cpu_freq = psutil.cpu_freq()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk I/O
        disk_io = psutil.disk_io_counters()
        
        # Network I/O
        net_io = psutil.net_io_counters()
        
        # Process metrics
        ray_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            if 'ray' in proc.info['name'].lower():
                ray_processes.append(proc.info)
                
        return {
            'hostname': self.hostname,
            'timestamp': datetime.utcnow().isoformat(),
            'cpu': {
                'count': psutil.cpu_count(),
                'percent': sum(cpu_percent) / len(cpu_percent),
                'per_cpu': cpu_percent,
                'frequency_mhz': cpu_freq.current if cpu_freq else 0
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent,
                'swap_used': swap.used,
                'swap_percent': swap.percent
            },
            'disk_io': {
                'read_bytes': disk_io.read_bytes,
                'write_bytes': disk_io.write_bytes,
                'read_count': disk_io.read_count,
                'write_count': disk_io.write_count
            },
            'network_io': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            },
            'ray_processes': ray_processes
        }
        
    def update_prometheus_gpu_metrics(self, metrics):
        """Update Prometheus metrics"""
        if not PROMETHEUS_AVAILABLE:
            return
            
        gpu_index = str(metrics['index'])
        gpu_name = metrics['name']
        
        self.gpu_utilization.labels(gpu_index=gpu_index, gpu_name=gpu_name).set(metrics['gpu_utilization'])
        self.gpu_memory_used.labels(gpu_index=gpu_index, gpu_name=gpu_name).set(metrics['memory_used'])
        self.gpu_memory_total.labels(gpu_index=gpu_index, gpu_name=gpu_name).set(metrics['memory_total'])
        self.gpu_temperature.labels(gpu_index=gpu_index, gpu_name=gpu_name).set(metrics['temperature'])
        self.gpu_power_usage.labels(gpu_index=gpu_index, gpu_name=gpu_name).set(metrics['power_watts'])
        
        if 'estimated_tensor_core_util' in metrics:
            self.gpu_tensor_core_util.labels(gpu_index=gpu_index, gpu_name=gpu_name).set(metrics['estimated_tensor_core_util'])
            
    def write_metrics_to_file(self, metrics):
        """Write metrics to JSON file"""
        metrics_file = os.path.join(self.snap_data, 'gpu-metrics.json')
        
        try:
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        except Exception as e:
            print(f"Error writing metrics file: {e}")
            
    def run(self):
        """Main monitoring loop"""
        print(f"Advanced GPU Monitor started on {self.hostname}")
        print(f"GPU Architecture: {self.gpu_architecture}")
        print(f"Monitoring interval: 30 seconds")
        
        # Start Prometheus HTTP server if available
        if PROMETHEUS_AVAILABLE:
            start_http_server(9090)
            print("Prometheus metrics available at :9090/metrics")
            
        while True:
            try:
                # Collect all metrics
                metrics = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'hostname': self.hostname,
                    'gpu_architecture': self.gpu_architecture,
                    'gpus': self.get_gpu_metrics(),
                    'infiniband': self.get_infiniband_metrics(),
                    'system': self.get_system_metrics()
                }
                
                # Write to file
                self.write_metrics_to_file(metrics)
                
                # Log summary
                gpu_count = len(metrics['gpus'])
                if gpu_count > 0:
                    avg_gpu_util = sum(g['gpu_utilization'] for g in metrics['gpus']) / gpu_count
                    avg_gpu_temp = sum(g['temperature'] for g in metrics['gpus']) / gpu_count
                    total_power = sum(g['power_watts'] for g in metrics['gpus'])
                    
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"GPUs: {gpu_count}, "
                          f"Avg Util: {avg_gpu_util:.1f}%, "
                          f"Avg Temp: {avg_gpu_temp:.1f}°C, "
                          f"Total Power: {total_power:.1f}W, "
                          f"CPU: {metrics['system']['cpu']['percent']:.1f}%, "
                          f"Memory: {metrics['system']['memory']['percent']:.1f}%")
                          
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                
            time.sleep(30)

if __name__ == '__main__':
    monitor = AdvancedGPUMonitor()
    monitor.run()