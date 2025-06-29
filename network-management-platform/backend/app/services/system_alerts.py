"""
System alerts service for automated issue creation and monitoring.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from app.services.github_integration import github_service
from app.services.websocket_service import websocket_manager
from app.models.notification import NotificationType, NotificationSource
from app.core.logging_config import logger
from app.db.session import AsyncSessionLocal
from app.models.device import Device
from app.models.metric import Metric
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert type enumeration"""
    DEVICE_DOWN = "device_down"
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    DISK_SPACE = "disk_space"
    NETWORK_ERROR = "network_error"
    SECURITY_THREAT = "security_threat"
    BACKUP_FAILURE = "backup_failure"
    SERVICE_DEGRADATION = "service_degradation"


class SystemAlertService:
    """Service for managing system alerts and automated issue creation"""
    
    def __init__(self):
        self.alert_thresholds = {
            "cpu_usage": 85.0,  # Percentage
            "memory_usage": 90.0,  # Percentage
            "disk_usage": 85.0,  # Percentage
            "network_error_rate": 5.0,  # Percentage
            "response_time": 5000,  # Milliseconds
        }
        self.alert_cooldown = 3600  # 1 hour in seconds
        self.active_alerts: Dict[str, datetime] = {}
        self.monitoring_interval = 300  # 5 minutes
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self):
        """Start system monitoring for alerts"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("System alert monitoring already running")
            return
        
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started system alert monitoring")
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped system alert monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._check_system_health()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _check_system_health(self):
        """Check overall system health and trigger alerts"""
        try:
            async with AsyncSessionLocal() as session:
                # Check device health
                await self._check_device_health(session)
                
                # Check system metrics
                await self._check_system_metrics(session)
                
                # Check backup status
                await self._check_backup_status(session)
                
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
    
    async def _check_device_health(self, session: AsyncSession):
        """Check health of all devices"""
        try:
            # Get all active devices
            result = await session.execute(
                select(Device).where(Device.is_active == True)
            )
            devices = result.scalars().all()
            
            now = datetime.utcnow()
            for device in devices:
                # Check if device is responding
                if device.last_seen:
                    time_since_seen = (now - device.last_seen).total_seconds()
                    if time_since_seen > 600:  # 10 minutes
                        await self._create_alert(
                            alert_type=AlertType.DEVICE_DOWN,
                            severity=AlertSeverity.HIGH,
                            title=f"Device {device.name} is not responding",
                            description=f"Device {device.name} ({device.ip_address}) has not been seen for {int(time_since_seen / 60)} minutes",
                            device_id=device.id,
                            metadata={
                                "device_name": device.name,
                                "ip_address": device.ip_address,
                                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                            }
                        )
                
        except Exception as e:
            logger.error(f"Error checking device health: {e}")
    
    async def _check_system_metrics(self, session: AsyncSession):
        """Check system metrics for anomalies"""
        try:
            # Get recent metrics
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            result = await session.execute(
                select(Metric).where(
                    Metric.timestamp > one_hour_ago
                ).order_by(Metric.timestamp.desc())
            )
            metrics = result.scalars().all()
            
            # Group metrics by device
            device_metrics: Dict[int, List[Metric]] = {}
            for metric in metrics:
                if metric.device_id not in device_metrics:
                    device_metrics[metric.device_id] = []
                device_metrics[metric.device_id].append(metric)
            
            # Analyze metrics for each device
            for device_id, metrics_list in device_metrics.items():
                await self._analyze_device_metrics(device_id, metrics_list)
                
        except Exception as e:
            logger.error(f"Error checking system metrics: {e}")
    
    async def _analyze_device_metrics(self, device_id: int, metrics: List[Metric]):
        """Analyze metrics for a specific device"""
        try:
            # Calculate averages
            cpu_values = [m.value for m in metrics if m.metric_type == "cpu_usage"]
            memory_values = [m.value for m in metrics if m.metric_type == "memory_usage"]
            disk_values = [m.value for m in metrics if m.metric_type == "disk_usage"]
            
            # Check CPU usage
            if cpu_values:
                avg_cpu = sum(cpu_values) / len(cpu_values)
                if avg_cpu > self.alert_thresholds["cpu_usage"]:
                    await self._create_alert(
                        alert_type=AlertType.HIGH_CPU,
                        severity=AlertSeverity.MEDIUM if avg_cpu < 95 else AlertSeverity.HIGH,
                        title=f"High CPU usage on device",
                        description=f"Average CPU usage is {avg_cpu:.1f}% over the last hour",
                        device_id=device_id,
                        metadata={
                            "avg_cpu": avg_cpu,
                            "threshold": self.alert_thresholds["cpu_usage"],
                            "samples": len(cpu_values),
                        }
                    )
            
            # Check memory usage
            if memory_values:
                avg_memory = sum(memory_values) / len(memory_values)
                if avg_memory > self.alert_thresholds["memory_usage"]:
                    await self._create_alert(
                        alert_type=AlertType.HIGH_MEMORY,
                        severity=AlertSeverity.MEDIUM if avg_memory < 95 else AlertSeverity.HIGH,
                        title=f"High memory usage on device",
                        description=f"Average memory usage is {avg_memory:.1f}% over the last hour",
                        device_id=device_id,
                        metadata={
                            "avg_memory": avg_memory,
                            "threshold": self.alert_thresholds["memory_usage"],
                            "samples": len(memory_values),
                        }
                    )
            
            # Check disk usage
            if disk_values:
                current_disk = disk_values[0]  # Most recent
                if current_disk > self.alert_thresholds["disk_usage"]:
                    await self._create_alert(
                        alert_type=AlertType.DISK_SPACE,
                        severity=AlertSeverity.HIGH if current_disk > 95 else AlertSeverity.MEDIUM,
                        title=f"Low disk space on device",
                        description=f"Disk usage is at {current_disk:.1f}%",
                        device_id=device_id,
                        metadata={
                            "disk_usage": current_disk,
                            "threshold": self.alert_thresholds["disk_usage"],
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error analyzing device metrics: {e}")
    
    async def _check_backup_status(self, session: AsyncSession):
        """Check backup status and alert on failures"""
        # This would check backup job status from the database
        # For now, it's a placeholder
        pass
    
    async def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        device_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Create an alert and optionally a GitHub issue"""
        try:
            # Check cooldown
            alert_key = f"{alert_type}_{device_id}"
            if alert_key in self.active_alerts:
                time_since_last = (datetime.utcnow() - self.active_alerts[alert_key]).total_seconds()
                if time_since_last < self.alert_cooldown:
                    logger.debug(f"Alert {alert_key} in cooldown period")
                    return
            
            # Update active alerts
            self.active_alerts[alert_key] = datetime.utcnow()
            
            # Log the alert
            logger.warning(f"System Alert: {title} - {description}")
            
            # Create GitHub issue for high/critical alerts
            if severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
                await self._create_github_issue(
                    alert_type=alert_type,
                    severity=severity,
                    title=title,
                    description=description,
                    metadata=metadata
                )
            
            # Broadcast alert via WebSocket
            await self._broadcast_alert(
                alert_type=alert_type,
                severity=severity,
                title=title,
                description=description,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def _create_github_issue(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Create a GitHub issue for the alert"""
        try:
            # Prepare issue body
            issue_body = f"""## System Alert: {alert_type.value}

**Severity:** {severity.value.upper()}
**Timestamp:** {datetime.utcnow().isoformat()}

### Description
{description}

### Details
```json
{json.dumps(metadata or {}, indent=2)}
```

### Automated Response
This issue was automatically created by the Network Management Platform alert system.

**Alert Type:** `{alert_type.value}`
**Component:** Network Management Platform
"""
            
            # Determine labels based on alert type and severity
            labels = [f"severity:{severity.value}", "automated", "alert"]
            
            if alert_type in [AlertType.DEVICE_DOWN, AlertType.HIGH_CPU, AlertType.HIGH_MEMORY]:
                labels.append("infrastructure")
            elif alert_type == AlertType.SECURITY_THREAT:
                labels.append("security")
            elif alert_type == AlertType.BACKUP_FAILURE:
                labels.append("backup")
            
            # Create issue
            async with github_service as service:
                issue = await service.create_issue(
                    title=f"[Alert] {title}",
                    body=issue_body,
                    labels=labels
                )
                
                logger.info(f"Created GitHub issue #{issue.get('number')} for alert: {title}")
                
        except Exception as e:
            logger.error(f"Error creating GitHub issue for alert: {e}")
    
    async def _broadcast_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast alert via WebSocket"""
        try:
            alert_data = {
                "type": "system_alert",
                "alert_type": alert_type.value,
                "severity": severity.value,
                "title": title,
                "description": description,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            await websocket_manager.broadcast(json.dumps(alert_data))
            
        except Exception as e:
            logger.error(f"Error broadcasting alert: {e}")
    
    async def test_alert(self, alert_type: AlertType, severity: AlertSeverity) -> Dict[str, Any]:
        """Create a test alert for testing purposes"""
        test_metadata = {
            "test": True,
            "generated_at": datetime.utcnow().isoformat(),
            "test_value": 95.5,
        }
        
        await self._create_alert(
            alert_type=alert_type,
            severity=severity,
            title=f"Test Alert: {alert_type.value}",
            description=f"This is a test alert with severity {severity.value}",
            metadata=test_metadata
        )
        
        return {
            "status": "success",
            "alert_type": alert_type.value,
            "severity": severity.value,
            "message": "Test alert created successfully"
        }


# Singleton instance
system_alert_service = SystemAlertService()