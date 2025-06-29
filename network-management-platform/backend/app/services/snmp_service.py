"""
Enhanced SNMP service integrating with existing SNMP manager
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import asdict
import json

from app.core.database import get_db
from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager
from app.models.device import Device, DeviceMetric
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

# Import the existing SNMP manager
import sys
sys.path.append('/home/edward/network/src/network')
from snmp_manager import SNMPManager, SNMPDevice, SystemInfo, InterfaceInfo

logger = logging.getLogger(__name__)


class SNMPService:
    """Enhanced SNMP service for the network management platform"""
    
    def __init__(self):
        self.snmp_manager = SNMPManager(max_workers=20)
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.monitoring_intervals: Dict[str, int] = {}
        
    async def start_device_monitoring(self, device_id: str, db: AsyncSession, 
                                    interval: int = 300) -> bool:
        """Start continuous SNMP monitoring for a device"""
        try:
            # Get device from database
            result = await db.execute(select(Device).where(Device.id == device_id))
            device = result.scalar_one_or_none()
            
            if not device or not device.snmp_enabled:
                logger.warning(f"Device {device_id} not found or SNMP not enabled")
                return False
            
            # Stop existing monitoring if running
            await self.stop_device_monitoring(device_id)
            
            # Create SNMP device object
            snmp_device = SNMPDevice(
                ip_address=device.ip_address,
                community=device.snmp_community or "public",
                version=device.snmp_version or 2,
                port=device.snmp_port or 161,
                timeout=device.snmp_timeout or 5,
                retries=3
            )
            
            # Start monitoring task
            self.monitoring_intervals[device_id] = interval
            self.monitoring_tasks[device_id] = asyncio.create_task(
                self._monitor_device_loop(device_id, snmp_device, db, interval)
            )
            
            logger.info(f"Started SNMP monitoring for device {device_id} with {interval}s interval")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start SNMP monitoring for device {device_id}: {e}")
            return False
    
    async def stop_device_monitoring(self, device_id: str) -> bool:
        """Stop SNMP monitoring for a device"""
        try:
            if device_id in self.monitoring_tasks:
                task = self.monitoring_tasks[device_id]
                task.cancel()
                
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                del self.monitoring_tasks[device_id]
                if device_id in self.monitoring_intervals:
                    del self.monitoring_intervals[device_id]
                
                logger.info(f"Stopped SNMP monitoring for device {device_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to stop SNMP monitoring for device {device_id}: {e}")
            return False
    
    async def _monitor_device_loop(self, device_id: str, snmp_device: SNMPDevice,
                                 db: AsyncSession, interval: int):
        """Main monitoring loop for a device"""
        try:
            while True:
                try:
                    # Collect SNMP data
                    monitoring_data = await self.snmp_manager.monitor_device(snmp_device, interval)
                    
                    # Process and store the data
                    await self._process_monitoring_data(device_id, monitoring_data, db)
                    
                    # Broadcast to WebSocket clients
                    await websocket_manager.broadcast_snmp_data(device_id, monitoring_data)
                    
                    # Cache recent data
                    cache_key = f"snmp_data:{device_id}"
                    await cache_manager.set(cache_key, monitoring_data, ttl=interval * 2)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop for device {device_id}: {e}")
                    
                    # Send error notification
                    error_data = {
                        "device_id": device_id,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket_manager.broadcast_snmp_data(device_id, error_data)
                
                # Wait for next interval
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info(f"Monitoring cancelled for device {device_id}")
        except Exception as e:
            logger.error(f"Critical error in monitoring loop for device {device_id}: {e}")
    
    async def _process_monitoring_data(self, device_id: str, monitoring_data: Dict[str, Any],
                                     db: AsyncSession):
        """Process and store monitoring data in database"""
        try:
            timestamp = datetime.utcnow()
            
            # Store system metrics
            if monitoring_data.get('system_info'):
                system_info = monitoring_data['system_info']
                if isinstance(system_info, SystemInfo):
                    await self._store_system_metrics(device_id, system_info, timestamp, db)
            
            # Store CPU metrics
            if monitoring_data.get('cpu_usage') is not None:
                await self._store_metric(
                    device_id, "cpu_usage", monitoring_data['cpu_usage'], 
                    timestamp, db, unit="percent"
                )
            
            # Store memory metrics
            if monitoring_data.get('memory_usage'):
                memory_data = monitoring_data['memory_usage']
                await self._store_metric(
                    device_id, "memory_total", memory_data.get('total', 0),
                    timestamp, db, unit="bytes"
                )
                await self._store_metric(
                    device_id, "memory_used", memory_data.get('used', 0),
                    timestamp, db, unit="bytes"
                )
                await self._store_metric(
                    device_id, "memory_usage_percent", memory_data.get('usage_percent', 0),
                    timestamp, db, unit="percent"
                )
            
            # Store interface metrics
            if monitoring_data.get('interfaces'):
                for interface in monitoring_data['interfaces']:
                    if isinstance(interface, InterfaceInfo):
                        await self._store_interface_metrics(device_id, interface, timestamp, db)
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to process monitoring data for device {device_id}: {e}")
            await db.rollback()
    
    async def _store_system_metrics(self, device_id: str, system_info: SystemInfo,
                                  timestamp: datetime, db: AsyncSession):
        """Store system information metrics"""
        if system_info.uptime is not None:
            await self._store_metric(
                device_id, "uptime", system_info.uptime,
                timestamp, db, unit="seconds"
            )
    
    async def _store_interface_metrics(self, device_id: str, interface: InterfaceInfo,
                                     timestamp: datetime, db: AsyncSession):
        """Store interface metrics"""
        interface_prefix = f"interface_{interface.index}"
        
        # Traffic metrics
        await self._store_metric(
            device_id, f"{interface_prefix}_in_octets", interface.in_octets,
            timestamp, db, unit="bytes", metadata={"interface_name": interface.name}
        )
        await self._store_metric(
            device_id, f"{interface_prefix}_out_octets", interface.out_octets,
            timestamp, db, unit="bytes", metadata={"interface_name": interface.name}
        )
        
        # Error metrics
        await self._store_metric(
            device_id, f"{interface_prefix}_in_errors", interface.in_errors,
            timestamp, db, unit="count", metadata={"interface_name": interface.name}
        )
        await self._store_metric(
            device_id, f"{interface_prefix}_out_errors", interface.out_errors,
            timestamp, db, unit="count", metadata={"interface_name": interface.name}
        )
        
        # Status metrics
        await self._store_metric(
            device_id, f"{interface_prefix}_oper_status", interface.oper_status,
            timestamp, db, unit="status", metadata={"interface_name": interface.name}
        )
    
    async def _store_metric(self, device_id: str, metric_type: str, value: Any,
                          timestamp: datetime, db: AsyncSession, unit: str = "",
                          metadata: Optional[Dict[str, Any]] = None):
        """Store a single metric in the database"""
        try:
            metric = DeviceMetric(
                device_id=device_id,
                metric_type=metric_type,
                value=float(value) if value is not None else 0.0,
                unit=unit,
                timestamp=timestamp,
                metadata=metadata or {}
            )
            db.add(metric)
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to store metric {metric_type} for device {device_id}: {e}")
    
    async def get_device_snmp_status(self, device_id: str) -> Dict[str, Any]:
        """Get current SNMP monitoring status for a device"""
        is_monitoring = device_id in self.monitoring_tasks
        interval = self.monitoring_intervals.get(device_id, 0)
        
        # Get cached recent data
        cache_key = f"snmp_data:{device_id}"
        recent_data = await cache_manager.get(cache_key)
        
        return {
            "device_id": device_id,
            "monitoring_active": is_monitoring,
            "monitoring_interval": interval,
            "last_data": recent_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_all_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring status for all devices"""
        status = {}
        for device_id in self.monitoring_tasks.keys():
            status[device_id] = await self.get_device_snmp_status(device_id)
        
        return {
            "total_monitored_devices": len(self.monitoring_tasks),
            "devices": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def test_snmp_connectivity(self, ip_address: str, community: str = "public",
                                   version: int = 2, port: int = 161) -> Dict[str, Any]:
        """Test SNMP connectivity to a device"""
        try:
            snmp_device = SNMPDevice(
                ip_address=ip_address,
                community=community,
                version=version,
                port=port,
                timeout=10,
                retries=2
            )
            
            # Try to get basic system information
            system_info = await self.snmp_manager.get_system_info(snmp_device)
            
            if system_info:
                return {
                    "success": True,
                    "ip_address": ip_address,
                    "system_info": {
                        "hostname": system_info.hostname,
                        "description": system_info.description,
                        "uptime": system_info.uptime,
                        "contact": system_info.contact,
                        "location": system_info.location
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "success": False,
                    "ip_address": ip_address,
                    "error": "No response from SNMP agent",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "success": False,
                "ip_address": ip_address,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_interface_metrics_history(self, device_id: str, interface_index: int,
                                          hours: int = 24) -> Dict[str, Any]:
        """Get historical interface metrics"""
        try:
            async with get_db() as db:
                # Calculate time range
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=hours)
                
                # Query metrics for the interface
                result = await db.execute(
                    select(DeviceMetric).where(
                        and_(
                            DeviceMetric.device_id == device_id,
                            DeviceMetric.metric_type.like(f"interface_{interface_index}_%"),
                            DeviceMetric.timestamp >= start_time,
                            DeviceMetric.timestamp <= end_time
                        )
                    ).order_by(DeviceMetric.timestamp)
                )
                
                metrics = result.scalars().all()
                
                # Group metrics by type
                grouped_metrics = {}
                for metric in metrics:
                    metric_type = metric.metric_type
                    if metric_type not in grouped_metrics:
                        grouped_metrics[metric_type] = []
                    
                    grouped_metrics[metric_type].append({
                        "timestamp": metric.timestamp.isoformat(),
                        "value": metric.value,
                        "unit": metric.unit
                    })
                
                return {
                    "device_id": device_id,
                    "interface_index": interface_index,
                    "time_range": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                        "hours": hours
                    },
                    "metrics": grouped_metrics,
                    "total_data_points": len(metrics)
                }
                
        except Exception as e:
            logger.error(f"Failed to get interface metrics history: {e}")
            return {"error": str(e)}
    
    def cleanup(self):
        """Clean up resources"""
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        self.monitoring_tasks.clear()
        self.monitoring_intervals.clear()
        self.snmp_manager.close()


# Global SNMP service instance
snmp_service = SNMPService()