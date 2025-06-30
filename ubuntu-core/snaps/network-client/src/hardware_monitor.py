#!/usr/bin/env python3
"""
Hardware monitoring module for Ubuntu Core client snap.
Collects system metrics including CPU, memory, disk, temperature, and GPU stats.
"""

import os
import json
import time
import subprocess
import psutil
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class HardwareMonitor:
    """Hardware monitoring for Ubuntu Core environment"""
    
    def __init__(self):
        self.thermal_zones = self._discover_thermal_zones()
        self.has_nvidia_gpu = self._check_nvidia_gpu()
        self.smart_capable_drives = self._discover_smart_drives()
        
    def _discover_thermal_zones(self) -> List[Path]:
        """Discover available thermal zones in the system"""
        thermal_path = Path("/sys/devices/virtual/thermal")
        zones = []
        
        if thermal_path.exists():
            for zone in thermal_path.glob("thermal_zone*"):
                if (zone / "temp").exists():
                    zones.append(zone)
                    
        logger.info(f"Discovered {len(zones)} thermal zones")
        return zones
    
    def _check_nvidia_gpu(self) -> bool:
        """Check if NVIDIA GPU is available"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _discover_smart_drives(self) -> List[str]:
        """Discover drives that support SMART monitoring"""
        drives = []
        try:
            # List block devices
            result = subprocess.run(
                ["lsblk", "-dno", "NAME,TYPE"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "disk":
                        drive = f"/dev/{parts[0]}"
                        # Check if drive supports SMART
                        smart_check = subprocess.run(
                            ["smartctl", "-i", drive],
                            capture_output=True,
                            timeout=5
                        )
                        if smart_check.returncode == 0:
                            drives.append(drive)
                            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("smartctl not available or timeout occurred")
            
        logger.info(f"Found {len(drives)} SMART-capable drives")
        return drives
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information and usage"""
        try:
            # CPU usage per core
            cpu_percent_per_core = psutil.cpu_percent(interval=1, percpu=True)
            
            # CPU frequency
            cpu_freq = psutil.cpu_freq()
            
            # CPU stats
            cpu_stats = psutil.cpu_stats()
            
            # Load average
            load_avg = os.getloadavg()
            
            return {
                "usage_percent": psutil.cpu_percent(interval=1),
                "usage_per_core": cpu_percent_per_core,
                "core_count": psutil.cpu_count(logical=False),
                "thread_count": psutil.cpu_count(logical=True),
                "frequency": {
                    "current": cpu_freq.current if cpu_freq else None,
                    "min": cpu_freq.min if cpu_freq else None,
                    "max": cpu_freq.max if cpu_freq else None,
                },
                "stats": {
                    "ctx_switches": cpu_stats.ctx_switches,
                    "interrupts": cpu_stats.interrupts,
                    "soft_interrupts": cpu_stats.soft_interrupts,
                    "syscalls": cpu_stats.syscalls,
                },
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2],
                }
            }
        except Exception as e:
            logger.error(f"Error getting CPU info: {e}")
            return {}
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        try:
            # Virtual memory
            vm = psutil.virtual_memory()
            
            # Swap memory
            swap = psutil.swap_memory()
            
            return {
                "virtual": {
                    "total": vm.total,
                    "available": vm.available,
                    "used": vm.used,
                    "free": vm.free,
                    "percent": vm.percent,
                    "active": getattr(vm, 'active', None),
                    "inactive": getattr(vm, 'inactive', None),
                    "buffers": getattr(vm, 'buffers', None),
                    "cached": getattr(vm, 'cached', None),
                    "shared": getattr(vm, 'shared', None),
                },
                "swap": {
                    "total": swap.total,
                    "used": swap.used,
                    "free": swap.free,
                    "percent": swap.percent,
                    "sin": swap.sin,
                    "sout": swap.sout,
                }
            }
        except Exception as e:
            logger.error(f"Error getting memory info: {e}")
            return {}
    
    def get_disk_info(self) -> Dict[str, Any]:
        """Get disk usage and I/O information"""
        try:
            disk_info = {}
            
            # Disk partitions and usage
            partitions = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "opts": partition.opts,
                        "usage": {
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": usage.percent,
                        }
                    })
                except PermissionError:
                    continue
                    
            disk_info["partitions"] = partitions
            
            # Disk I/O statistics
            io_counters = psutil.disk_io_counters(perdisk=True)
            disk_info["io_stats"] = {
                disk: {
                    "read_count": counters.read_count,
                    "write_count": counters.write_count,
                    "read_bytes": counters.read_bytes,
                    "write_bytes": counters.write_bytes,
                    "read_time": counters.read_time,
                    "write_time": counters.write_time,
                }
                for disk, counters in io_counters.items()
            }
            
            # SMART data for capable drives
            smart_data = {}
            for drive in self.smart_capable_drives:
                smart_info = self._get_smart_data(drive)
                if smart_info:
                    smart_data[drive] = smart_info
                    
            if smart_data:
                disk_info["smart"] = smart_data
                
            return disk_info
            
        except Exception as e:
            logger.error(f"Error getting disk info: {e}")
            return {}
    
    def _get_smart_data(self, drive: str) -> Optional[Dict[str, Any]]:
        """Get SMART data for a drive"""
        try:
            # Get SMART health status
            health_result = subprocess.run(
                ["smartctl", "-H", drive],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            health_passed = "PASSED" in health_result.stdout
            
            # Get SMART attributes
            attr_result = subprocess.run(
                ["smartctl", "-A", drive],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Parse temperature from attributes
            temperature = None
            for line in attr_result.stdout.split('\n'):
                if "Temperature_Celsius" in line or "Airflow_Temperature_Cel" in line:
                    parts = line.split()
                    if len(parts) >= 10:
                        try:
                            temperature = int(parts[9])
                        except ValueError:
                            pass
                            
            return {
                "health_passed": health_passed,
                "temperature_celsius": temperature,
            }
            
        except Exception as e:
            logger.error(f"Error getting SMART data for {drive}: {e}")
            return None
    
    def get_temperature_info(self) -> Dict[str, Any]:
        """Get temperature sensor readings"""
        try:
            temps = {}
            
            # Read thermal zones
            for zone in self.thermal_zones:
                try:
                    temp_file = zone / "temp"
                    type_file = zone / "type"
                    
                    temp_value = int(temp_file.read_text().strip()) / 1000.0
                    zone_type = type_file.read_text().strip() if type_file.exists() else "unknown"
                    
                    zone_name = zone.name
                    temps[zone_name] = {
                        "type": zone_type,
                        "temperature": temp_value,
                    }
                except Exception as e:
                    logger.error(f"Error reading thermal zone {zone}: {e}")
                    
            # Try to get lm-sensors data
            try:
                result = subprocess.run(
                    ["sensors", "-j"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    sensors_data = json.loads(result.stdout)
                    temps["sensors"] = sensors_data
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
                logger.debug("lm-sensors not available or failed to parse output")
                
            return temps
            
        except Exception as e:
            logger.error(f"Error getting temperature info: {e}")
            return {}
    
    def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information (NVIDIA GPUs)"""
        if not self.has_nvidia_gpu:
            return {}
            
        try:
            # Query GPU information
            result = subprocess.run([
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free,power.draw,power.limit",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {}
                
            gpu_info = {"nvidia": []}
            
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 9:
                    gpu_info["nvidia"].append({
                        "name": parts[0],
                        "temperature": float(parts[1]) if parts[1] != "N/A" else None,
                        "utilization_gpu": float(parts[2]) if parts[2] != "N/A" else None,
                        "utilization_memory": float(parts[3]) if parts[3] != "N/A" else None,
                        "memory_total": float(parts[4]) if parts[4] != "N/A" else None,
                        "memory_used": float(parts[5]) if parts[5] != "N/A" else None,
                        "memory_free": float(parts[6]) if parts[6] != "N/A" else None,
                        "power_draw": float(parts[7]) if parts[7] != "N/A" else None,
                        "power_limit": float(parts[8]) if parts[8] != "N/A" else None,
                    })
                    
            return gpu_info
            
        except Exception as e:
            logger.error(f"Error getting GPU info: {e}")
            return {}
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network interface information"""
        try:
            # Network interfaces
            interfaces = {}
            for iface, addrs in psutil.net_if_addrs().items():
                interface_info = {"addresses": []}
                
                for addr in addrs:
                    addr_info = {
                        "family": addr.family.name,
                        "address": addr.address,
                    }
                    if addr.netmask:
                        addr_info["netmask"] = addr.netmask
                    if addr.broadcast:
                        addr_info["broadcast"] = addr.broadcast
                        
                    interface_info["addresses"].append(addr_info)
                    
                # Interface statistics
                stats = psutil.net_if_stats().get(iface)
                if stats:
                    interface_info["stats"] = {
                        "isup": stats.isup,
                        "duplex": stats.duplex.name if stats.duplex else None,
                        "speed": stats.speed,
                        "mtu": stats.mtu,
                    }
                    
                interfaces[iface] = interface_info
                
            # Network I/O counters
            io_counters = psutil.net_io_counters(pernic=True)
            
            return {
                "interfaces": interfaces,
                "io_counters": {
                    iface: {
                        "bytes_sent": counters.bytes_sent,
                        "bytes_recv": counters.bytes_recv,
                        "packets_sent": counters.packets_sent,
                        "packets_recv": counters.packets_recv,
                        "errin": counters.errin,
                        "errout": counters.errout,
                        "dropin": counters.dropin,
                        "dropout": counters.dropout,
                    }
                    for iface, counters in io_counters.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return {}
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all hardware metrics"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu": self.get_cpu_info(),
            "memory": self.get_memory_info(),
            "disk": self.get_disk_info(),
            "temperature": self.get_temperature_info(),
            "gpu": self.get_gpu_info(),
            "network": self.get_network_info(),
            "system": {
                "uptime": time.time() - psutil.boot_time(),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            }
        }


def main():
    """Test hardware monitoring"""
    logging.basicConfig(level=logging.INFO)
    
    monitor = HardwareMonitor()
    metrics = monitor.collect_all_metrics()
    
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()