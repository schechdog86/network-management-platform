"""
System management tools for LangChain
"""

from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
import subprocess
import psutil
import platform
import os
from datetime import datetime

from .base import BaseNetworkTool, NetworkToolInput, RequiresConfirmationMixin


class SystemInfoInput(BaseModel):
    """Input for system info tool"""
    target: Optional[str] = Field(None, description="Target system (local if not specified)")
    info_types: List[str] = Field(
        default=["basic", "cpu", "memory", "disk"],
        description="Types of information to gather"
    )


class SystemInfoTool(BaseNetworkTool):
    """Tool for gathering system information"""
    
    name: str = "system_info"
    description: str = "Get detailed system information including hardware, OS, and resource usage"
    args_schema: Type[BaseModel] = SystemInfoInput
    
    def _execute(self, target: Optional[str] = None, info_types: List[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Gather system information"""
        if target and target != "local":
            return {"error": "Remote system info requires SSH access (not implemented)"}
        
        if info_types is None:
            info_types = ["basic", "cpu", "memory", "disk"]
        
        info = {}
        
        if "basic" in info_types:
            info["basic"] = self._get_basic_info()
        if "cpu" in info_types:
            info["cpu"] = self._get_cpu_info()
        if "memory" in info_types:
            info["memory"] = self._get_memory_info()
        if "disk" in info_types:
            info["disk"] = self._get_disk_info()
        if "network" in info_types:
            info["network"] = self._get_network_info()
        if "processes" in info_types:
            info["processes"] = self._get_process_info()
        
        return info
    
    def _get_basic_info(self) -> Dict[str, Any]:
        """Get basic system information"""
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            "uptime_hours": round((datetime.now().timestamp() - psutil.boot_time()) / 3600, 2)
        }
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        cpu_freq = psutil.cpu_freq()
        return {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "current_frequency_mhz": cpu_freq.current if cpu_freq else None,
            "min_frequency_mhz": cpu_freq.min if cpu_freq else None,
            "max_frequency_mhz": cpu_freq.max if cpu_freq else None,
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "per_cpu_usage": psutil.cpu_percent(interval=1, percpu=True),
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        virtual_mem = psutil.virtual_memory()
        swap_mem = psutil.swap_memory()
        
        return {
            "virtual": {
                "total_gb": round(virtual_mem.total / (1024**3), 2),
                "available_gb": round(virtual_mem.available / (1024**3), 2),
                "used_gb": round(virtual_mem.used / (1024**3), 2),
                "free_gb": round(virtual_mem.free / (1024**3), 2),
                "percent_used": virtual_mem.percent
            },
            "swap": {
                "total_gb": round(swap_mem.total / (1024**3), 2),
                "used_gb": round(swap_mem.used / (1024**3), 2),
                "free_gb": round(swap_mem.free / (1024**3), 2),
                "percent_used": swap_mem.percent
            }
        }
    
    def _get_disk_info(self) -> Dict[str, Any]:
        """Get disk information"""
        partitions = []
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": usage.percent
                })
            except PermissionError:
                continue
        
        io_counters = psutil.disk_io_counters()
        
        return {
            "partitions": partitions,
            "io_statistics": {
                "read_count": io_counters.read_count,
                "write_count": io_counters.write_count,
                "read_gb": round(io_counters.read_bytes / (1024**3), 2),
                "write_gb": round(io_counters.write_bytes / (1024**3), 2)
            } if io_counters else None
        }
    
    def _get_network_info(self) -> Dict[str, Any]:
        """Get network interface information"""
        interfaces = {}
        
        for interface, addrs in psutil.net_if_addrs().items():
            interface_info = {
                "addresses": []
            }
            
            for addr in addrs:
                addr_info = {
                    "family": str(addr.family),
                    "address": addr.address
                }
                if addr.netmask:
                    addr_info["netmask"] = addr.netmask
                if addr.broadcast:
                    addr_info["broadcast"] = addr.broadcast
                
                interface_info["addresses"].append(addr_info)
            
            # Get interface statistics
            stats = psutil.net_if_stats().get(interface)
            if stats:
                interface_info["is_up"] = stats.isup
                interface_info["speed_mbps"] = stats.speed
            
            interfaces[interface] = interface_info
        
        io_counters = psutil.net_io_counters()
        
        return {
            "interfaces": interfaces,
            "io_statistics": {
                "bytes_sent_gb": round(io_counters.bytes_sent / (1024**3), 2),
                "bytes_received_gb": round(io_counters.bytes_recv / (1024**3), 2),
                "packets_sent": io_counters.packets_sent,
                "packets_received": io_counters.packets_recv,
                "errors_in": io_counters.errin,
                "errors_out": io_counters.errout
            } if io_counters else None
        }
    
    def _get_process_info(self) -> Dict[str, Any]:
        """Get top processes by CPU and memory"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort by CPU usage
        top_cpu = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]
        
        # Sort by memory usage
        top_memory = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:5]
        
        return {
            "total_processes": len(processes),
            "top_cpu_processes": top_cpu,
            "top_memory_processes": top_memory
        }


class ProcessListInput(BaseModel):
    """Input for process list tool"""
    filter_name: Optional[str] = Field(None, description="Filter processes by name")
    sort_by: str = Field(default="cpu", description="Sort by: cpu, memory, pid, name")
    limit: int = Field(default=20, description="Number of processes to return")


class ProcessListTool(BaseNetworkTool):
    """Tool for listing processes"""
    
    name: str = "process_list"
    description: str = "List running processes with CPU and memory usage"
    args_schema: Type[BaseModel] = ProcessListInput
    
    def _execute(self, filter_name: Optional[str] = None, sort_by: str = "cpu", limit: int = 20, timeout: int = 30) -> Dict[str, Any]:
        """List processes"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.info
                
                # Apply filter if specified
                if filter_name and filter_name.lower() not in pinfo['name'].lower():
                    continue
                
                # Get additional info
                proc_obj = psutil.Process(pinfo['pid'])
                pinfo['create_time'] = datetime.fromtimestamp(proc_obj.create_time()).isoformat()
                pinfo['num_threads'] = proc_obj.num_threads()
                
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort processes
        sort_keys = {
            'cpu': 'cpu_percent',
            'memory': 'memory_percent',
            'pid': 'pid',
            'name': 'name'
        }
        
        sort_key = sort_keys.get(sort_by, 'cpu_percent')
        processes.sort(key=lambda x: x[sort_key], reverse=sort_by in ['cpu', 'memory'])
        
        # Limit results
        processes = processes[:limit]
        
        return {
            "total_found": len(processes),
            "sort_by": sort_by,
            "processes": processes
        }


class ServiceManagementInput(BaseModel):
    """Input for service management"""
    service_name: str = Field(description="Name of the service")
    action: str = Field(description="Action to perform: status, start, stop, restart")


class ServiceManagementTool(BaseNetworkTool, RequiresConfirmationMixin):
    """Tool for managing system services"""
    
    name: str = "service_management"
    description: str = "Manage system services (start, stop, restart, check status)"
    args_schema: Type[BaseModel] = ServiceManagementInput
    
    def _execute(self, service_name: str, action: str, timeout: int = 30) -> Dict[str, Any]:
        """Manage service"""
        valid_actions = ["status", "start", "stop", "restart"]
        
        if action not in valid_actions:
            return {"error": f"Invalid action: {action}. Valid actions: {valid_actions}"}
        
        # Confirm destructive actions
        if action in ["stop", "restart"] and self.requires_confirmation:
            if not self.get_confirmation(f"{action} service {service_name}"):
                return {"cancelled": True, "reason": "User cancelled action"}
        
        # Determine system init
        init_system = self._detect_init_system()
        
        if init_system == "systemd":
            return self._systemd_action(service_name, action)
        elif init_system == "init.d":
            return self._initd_action(service_name, action)
        else:
            return {"error": "Unknown init system"}
    
    def _detect_init_system(self) -> str:
        """Detect the init system"""
        if os.path.exists("/run/systemd/system"):
            return "systemd"
        elif os.path.exists("/etc/init.d"):
            return "init.d"
        else:
            return "unknown"
    
    def _systemd_action(self, service: str, action: str) -> Dict[str, Any]:
        """Perform systemd action"""
        try:
            if action == "status":
                cmd = ["systemctl", "status", service]
            else:
                cmd = ["sudo", "systemctl", action, service]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            return {
                "service": service,
                "action": action,
                "success": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else result.stderr
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _initd_action(self, service: str, action: str) -> Dict[str, Any]:
        """Perform init.d action"""
        try:
            cmd = ["sudo", f"/etc/init.d/{service}", action]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            return {
                "service": service,
                "action": action,
                "success": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else result.stderr
            }
        except Exception as e:
            return {"error": str(e)}


class LogAnalysisInput(BaseModel):
    """Input for log analysis"""
    log_file: str = Field(description="Path to log file or 'syslog' for system log")
    lines: int = Field(default=100, description="Number of lines to analyze")
    filter_pattern: Optional[str] = Field(None, description="Pattern to filter log entries")
    severity: Optional[str] = Field(None, description="Filter by severity: error, warning, info")


class LogAnalysisTool(BaseNetworkTool):
    """Tool for analyzing system logs"""
    
    name: str = "log_analysis"
    description: str = "Analyze system or application logs for errors, warnings, and patterns"
    args_schema: Type[BaseModel] = LogAnalysisInput
    
    def _execute(self, log_file: str, lines: int = 100, filter_pattern: Optional[str] = None, 
                 severity: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Analyze logs"""
        if log_file == "syslog":
            log_file = "/var/log/syslog" if os.path.exists("/var/log/syslog") else "/var/log/messages"
        
        if not os.path.exists(log_file):
            return {"error": f"Log file not found: {log_file}"}
        
        try:
            # Read last N lines
            cmd = ["tail", "-n", str(lines), log_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {"error": f"Failed to read log: {result.stderr}"}
            
            log_lines = result.stdout.split('\n')
            
            # Filter lines
            filtered_lines = []
            stats = {
                "total_lines": len(log_lines),
                "errors": 0,
                "warnings": 0,
                "info": 0
            }
            
            for line in log_lines:
                if not line.strip():
                    continue
                
                # Apply pattern filter
                if filter_pattern and filter_pattern.lower() not in line.lower():
                    continue
                
                # Check severity
                line_lower = line.lower()
                if "error" in line_lower or "fail" in line_lower:
                    stats["errors"] += 1
                    if severity in [None, "error"]:
                        filtered_lines.append({"severity": "error", "message": line})
                elif "warn" in line_lower:
                    stats["warnings"] += 1
                    if severity in [None, "warning"]:
                        filtered_lines.append({"severity": "warning", "message": line})
                else:
                    stats["info"] += 1
                    if severity in [None, "info"]:
                        filtered_lines.append({"severity": "info", "message": line})
            
            return {
                "log_file": log_file,
                "statistics": stats,
                "filtered_entries": filtered_lines[:50],  # Limit output
                "total_filtered": len(filtered_lines)
            }
            
        except Exception as e:
            return {"error": str(e)}


class ResourceMonitorInput(BaseModel):
    """Input for resource monitoring"""
    duration: int = Field(default=5, description="Duration to monitor in seconds")
    interval: int = Field(default=1, description="Sampling interval in seconds")


class ResourceMonitorTool(BaseNetworkTool):
    """Tool for monitoring system resources"""
    
    name: str = "resource_monitor"
    description: str = "Monitor system resources (CPU, memory, disk, network) over time"
    args_schema: Type[BaseModel] = ResourceMonitorInput
    
    def _execute(self, duration: int = 5, interval: int = 1, timeout: int = 30) -> Dict[str, Any]:
        """Monitor resources"""
        samples = []
        start_time = datetime.now()
        
        # Initial network counters
        net_io_start = psutil.net_io_counters()
        
        for i in range(duration):
            sample = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": psutil.cpu_percent(interval=interval),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_io": {
                    "read_mb_s": 0,
                    "write_mb_s": 0
                },
                "network_io": {
                    "sent_mb_s": 0,
                    "recv_mb_s": 0
                }
            }
            
            # Calculate disk I/O rates
            disk_io = psutil.disk_io_counters()
            if disk_io and i > 0:
                prev_disk = samples[-1].get("_disk_io", {})
                if prev_disk:
                    sample["disk_io"]["read_mb_s"] = round(
                        (disk_io.read_bytes - prev_disk.get("read_bytes", 0)) / (interval * 1024 * 1024), 2
                    )
                    sample["disk_io"]["write_mb_s"] = round(
                        (disk_io.write_bytes - prev_disk.get("write_bytes", 0)) / (interval * 1024 * 1024), 2
                    )
            
            sample["_disk_io"] = {"read_bytes": disk_io.read_bytes, "write_bytes": disk_io.write_bytes} if disk_io else {}
            
            # Calculate network I/O rates
            net_io = psutil.net_io_counters()
            if net_io and i > 0:
                sample["network_io"]["sent_mb_s"] = round(
                    (net_io.bytes_sent - net_io_start.bytes_sent) / ((i * interval) * 1024 * 1024), 2
                )
                sample["network_io"]["recv_mb_s"] = round(
                    (net_io.bytes_recv - net_io_start.bytes_recv) / ((i * interval) * 1024 * 1024), 2
                )
            
            # Remove internal fields
            sample.pop("_disk_io", None)
            samples.append(sample)
        
        # Calculate averages
        avg_cpu = sum(s["cpu_percent"] for s in samples) / len(samples)
        avg_memory = sum(s["memory_percent"] for s in samples) / len(samples)
        
        return {
            "duration_seconds": duration,
            "samples_collected": len(samples),
            "averages": {
                "cpu_percent": round(avg_cpu, 2),
                "memory_percent": round(avg_memory, 2)
            },
            "samples": samples
        }