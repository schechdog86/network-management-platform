"""
Real-time system metrics collection service
"""

import asyncio
import psutil
import logging
import platform
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager
from app.core.database import get_db
from app.models.device import DeviceMetric
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SystemMetricsCollector:
    """Collects and broadcasts real-time system metrics"""
    
    def __init__(self):
        self.collection_task: Optional[asyncio.Task] = None
        self.collection_interval = 5  # seconds
        self.is_collecting = False
        self.metrics_history: List[Dict[str, Any]] = []
        self.max_history_size = 720  # 1 hour at 5-second intervals
        
    async def start_collection(self, interval: int = 5) -> bool:
        """Start system metrics collection"""
        try:
            if self.is_collecting:
                logger.warning("Metrics collection already running")
                return True
            
            self.collection_interval = interval
            self.is_collecting = True
            
            self.collection_task = asyncio.create_task(self._collection_loop())
            
            logger.info(f"Started system metrics collection with {interval}s interval")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start metrics collection: {e}")
            return False
    
    async def stop_collection(self) -> bool:
        """Stop system metrics collection"""
        try:
            if not self.is_collecting:
                return True
            
            self.is_collecting = False
            
            if self.collection_task:
                self.collection_task.cancel()
                try:
                    await self.collection_task
                except asyncio.CancelledError:
                    pass
                self.collection_task = None
            
            logger.info("Stopped system metrics collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop metrics collection: {e}")
            return False
    
    async def _collection_loop(self):
        """Main metrics collection loop"""
        try:
            while self.is_collecting:
                try:
                    # Collect all metrics
                    metrics = await self._collect_all_metrics()
                    
                    # Store in history
                    self._store_in_history(metrics)
                    
                    # Cache current metrics
                    await cache_manager.set("current_system_metrics", metrics, ttl=60)
                    
                    # Broadcast to WebSocket clients
                    await websocket_manager.broadcast_system_metrics(metrics)
                    
                    # Store in database every 30 seconds
                    if len(self.metrics_history) % 6 == 0:  # Every 6th collection (30s)
                        await self._store_metrics_to_db(metrics)
                    
                except Exception as e:
                    logger.error(f"Error in metrics collection loop: {e}")
                
                await asyncio.sleep(self.collection_interval)
                
        except asyncio.CancelledError:
            logger.info("Metrics collection loop cancelled")
        except Exception as e:
            logger.error(f"Critical error in metrics collection loop: {e}")
    
    async def _collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all system metrics"""
        timestamp = datetime.utcnow()
        
        # Run all metric collections concurrently
        tasks = [
            self._get_cpu_metrics(),
            self._get_memory_metrics(),
            self._get_disk_metrics(),
            self._get_network_metrics(),
            self._get_system_info(),
            self._get_process_metrics()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine all metrics
        metrics = {
            "timestamp": timestamp.isoformat(),
            "collection_interval": self.collection_interval,
            "hostname": platform.node(),
            "platform": platform.system(),
            "cpu": results[0] if not isinstance(results[0], Exception) else {},
            "memory": results[1] if not isinstance(results[1], Exception) else {},
            "disk": results[2] if not isinstance(results[2], Exception) else {},
            "network": results[3] if not isinstance(results[3], Exception) else {},
            "system": results[4] if not isinstance(results[4], Exception) else {},
            "processes": results[5] if not isinstance(results[5], Exception) else {}
        }
        
        return metrics
    
    async def _get_cpu_metrics(self) -> Dict[str, Any]:
        """Get CPU metrics"""
        try:
            # Get CPU usage per core
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            cpu_count = psutil.cpu_count()
            cpu_count_logical = psutil.cpu_count(logical=True)
            
            # Get CPU frequency
            cpu_freq = psutil.cpu_freq()
            
            # Get load average (Unix only)
            load_avg = None
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                pass  # Windows doesn't have load average
            
            # Get CPU times
            cpu_times = psutil.cpu_times()
            
            return {
                "usage_percent": psutil.cpu_percent(),
                "usage_per_core": cpu_percent,
                "count_physical": cpu_count,
                "count_logical": cpu_count_logical,
                "frequency": {
                    "current": cpu_freq.current if cpu_freq else None,
                    "min": cpu_freq.min if cpu_freq else None,
                    "max": cpu_freq.max if cpu_freq else None
                },
                "load_average": list(load_avg) if load_avg else None,
                "times": {
                    "user": cpu_times.user,
                    "system": cpu_times.system,
                    "idle": cpu_times.idle,
                    "nice": getattr(cpu_times, 'nice', 0),
                    "iowait": getattr(cpu_times, 'iowait', 0),
                    "irq": getattr(cpu_times, 'irq', 0),
                    "softirq": getattr(cpu_times, 'softirq', 0)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get CPU metrics: {e}")
            return {}
    
    async def _get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory metrics"""
        try:
            virtual_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()
            
            return {
                "virtual": {
                    "total": virtual_memory.total,
                    "available": virtual_memory.available,
                    "used": virtual_memory.used,
                    "free": virtual_memory.free,
                    "percent": virtual_memory.percent,
                    "active": getattr(virtual_memory, 'active', 0),
                    "inactive": getattr(virtual_memory, 'inactive', 0),
                    "buffers": getattr(virtual_memory, 'buffers', 0),
                    "cached": getattr(virtual_memory, 'cached', 0)
                },
                "swap": {
                    "total": swap_memory.total,
                    "used": swap_memory.used,
                    "free": swap_memory.free,
                    "percent": swap_memory.percent
                }
            }
        except Exception as e:
            logger.error(f"Failed to get memory metrics: {e}")
            return {}
    
    async def _get_disk_metrics(self) -> Dict[str, Any]:
        """Get disk metrics"""
        try:
            disk_partitions = psutil.disk_partitions()
            disk_info = []
            
            for partition in disk_partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "filesystem": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": (usage.used / usage.total) * 100 if usage.total > 0 else 0
                    })
                except PermissionError:
                    # Skip inaccessible partitions
                    continue
            
            # Get disk I/O statistics
            disk_io = psutil.disk_io_counters()
            disk_io_per_disk = psutil.disk_io_counters(perdisk=True)
            
            return {
                "partitions": disk_info,
                "io": {
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0,
                    "read_bytes": disk_io.read_bytes if disk_io else 0,
                    "write_bytes": disk_io.write_bytes if disk_io else 0,
                    "read_time": disk_io.read_time if disk_io else 0,
                    "write_time": disk_io.write_time if disk_io else 0
                },
                "io_per_disk": {
                    disk: {
                        "read_count": stats.read_count,
                        "write_count": stats.write_count,
                        "read_bytes": stats.read_bytes,
                        "write_bytes": stats.write_bytes
                    }
                    for disk, stats in (disk_io_per_disk or {}).items()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get disk metrics: {e}")
            return {}
    
    async def _get_network_metrics(self) -> Dict[str, Any]:
        """Get network metrics"""
        try:
            # Get network I/O statistics
            net_io = psutil.net_io_counters()
            net_io_per_interface = psutil.net_io_counters(pernic=True)
            
            # Get network interface addresses
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            interfaces = {}
            for interface, addresses in net_if_addrs.items():
                interface_info = {
                    "addresses": [],
                    "stats": {}
                }
                
                # Get addresses
                for addr in addresses:
                    addr_info = {
                        "family": addr.family.name if hasattr(addr.family, 'name') else str(addr.family),
                        "address": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast
                    }
                    interface_info["addresses"].append(addr_info)
                
                # Get interface statistics
                if interface in net_if_stats:
                    stats = net_if_stats[interface]
                    interface_info["stats"] = {
                        "isup": stats.isup,
                        "duplex": stats.duplex.name if hasattr(stats.duplex, 'name') else str(stats.duplex),
                        "speed": stats.speed,
                        "mtu": stats.mtu
                    }
                
                # Get I/O statistics
                if interface in net_io_per_interface:
                    io_stats = net_io_per_interface[interface]
                    interface_info["io"] = {
                        "bytes_sent": io_stats.bytes_sent,
                        "bytes_recv": io_stats.bytes_recv,
                        "packets_sent": io_stats.packets_sent,
                        "packets_recv": io_stats.packets_recv,
                        "errin": io_stats.errin,
                        "errout": io_stats.errout,
                        "dropin": io_stats.dropin,
                        "dropout": io_stats.dropout
                    }
                
                interfaces[interface] = interface_info
            
            return {
                "total_io": {
                    "bytes_sent": net_io.bytes_sent if net_io else 0,
                    "bytes_recv": net_io.bytes_recv if net_io else 0,
                    "packets_sent": net_io.packets_sent if net_io else 0,
                    "packets_recv": net_io.packets_recv if net_io else 0,
                    "errin": net_io.errin if net_io else 0,
                    "errout": net_io.errout if net_io else 0,
                    "dropin": net_io.dropin if net_io else 0,
                    "dropout": net_io.dropout if net_io else 0
                },
                "interfaces": interfaces
            }
        except Exception as e:
            logger.error(f"Failed to get network metrics: {e}")
            return {}
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        try:
            boot_time = psutil.boot_time()
            uptime = datetime.utcnow().timestamp() - boot_time
            
            return {
                "hostname": platform.node(),
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "boot_time": datetime.fromtimestamp(boot_time).isoformat(),
                "uptime_seconds": uptime,
                "python_version": platform.python_version(),
                "users": [
                    {
                        "name": user.name,
                        "terminal": user.terminal,
                        "host": user.host,
                        "started": datetime.fromtimestamp(user.started).isoformat()
                    }
                    for user in psutil.users()
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}
    
    async def _get_process_metrics(self) -> Dict[str, Any]:
        """Get process metrics"""
        try:
            processes = []
            process_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    process_count += 1
                    # Only include top processes to avoid overwhelming the data
                    if len(processes) < 10:
                        processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            
            return {
                "total_count": process_count,
                "top_processes": processes[:10]  # Top 10 by CPU usage
            }
        except Exception as e:
            logger.error(f"Failed to get process metrics: {e}")
            return {}
    
    def _store_in_history(self, metrics: Dict[str, Any]):
        """Store metrics in memory history"""
        self.metrics_history.append(metrics)
        
        # Keep only recent history
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
    
    async def _store_metrics_to_db(self, metrics: Dict[str, Any]):
        """Store metrics to database"""
        try:
            async with get_db() as db:
                timestamp = datetime.fromisoformat(metrics["timestamp"])
                hostname = metrics.get("hostname", "localhost")
                
                # Store key metrics as device metrics for the local system
                device_id = f"system_{hostname}"
                
                # CPU metrics
                if "cpu" in metrics and metrics["cpu"]:
                    cpu_data = metrics["cpu"]
                    await self._store_metric(
                        db, device_id, "cpu_usage_percent", 
                        cpu_data.get("usage_percent", 0), timestamp
                    )
                
                # Memory metrics
                if "memory" in metrics and metrics["memory"]:
                    memory_data = metrics["memory"].get("virtual", {})
                    await self._store_metric(
                        db, device_id, "memory_usage_percent",
                        memory_data.get("percent", 0), timestamp
                    )
                    await self._store_metric(
                        db, device_id, "memory_total_bytes",
                        memory_data.get("total", 0), timestamp
                    )
                    await self._store_metric(
                        db, device_id, "memory_used_bytes",
                        memory_data.get("used", 0), timestamp
                    )
                
                # Disk metrics
                if "disk" in metrics and metrics["disk"]:
                    disk_io = metrics["disk"].get("io", {})
                    await self._store_metric(
                        db, device_id, "disk_read_bytes",
                        disk_io.get("read_bytes", 0), timestamp
                    )
                    await self._store_metric(
                        db, device_id, "disk_write_bytes",
                        disk_io.get("write_bytes", 0), timestamp
                    )
                
                # Network metrics
                if "network" in metrics and metrics["network"]:
                    net_io = metrics["network"].get("total_io", {})
                    await self._store_metric(
                        db, device_id, "network_bytes_sent",
                        net_io.get("bytes_sent", 0), timestamp
                    )
                    await self._store_metric(
                        db, device_id, "network_bytes_recv",
                        net_io.get("bytes_recv", 0), timestamp
                    )
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to store metrics to database: {e}")
    
    async def _store_metric(self, db: AsyncSession, device_id: str, 
                          metric_type: str, value: float, timestamp: datetime):
        """Store a single metric to database"""
        try:
            metric = DeviceMetric(
                device_id=device_id,
                metric_type=metric_type,
                value=value,
                timestamp=timestamp,
                unit="",
                metadata={}
            )
            db.add(metric)
        except Exception as e:
            logger.error(f"Failed to create metric {metric_type}: {e}")
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        cached_metrics = await cache_manager.get("current_system_metrics")
        if cached_metrics:
            return cached_metrics
        
        # If no cached metrics, collect fresh ones
        return await self._collect_all_metrics()
    
    async def get_metrics_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get metrics history for specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            metrics for metrics in self.metrics_history
            if datetime.fromisoformat(metrics["timestamp"]) >= cutoff_time
        ]
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get metrics collection status"""
        return {
            "is_collecting": self.is_collecting,
            "collection_interval": self.collection_interval,
            "history_size": len(self.metrics_history),
            "max_history_size": self.max_history_size,
            "task_active": self.collection_task is not None and not self.collection_task.done()
        }


# Global system metrics collector instance
system_metrics_collector = SystemMetricsCollector()