"""
Snap Distribution Service
Manages enterprise snap distribution, progressive rollouts, and private store integration
"""

import asyncio
import logging
import json
import hashlib
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from pathlib import Path

try:
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.redis_client import cache_manager
    from app.services.websocket_manager import websocket_manager
    from app.services.snapd_service import snapd_service, SnapInfo, SnapChange
    from app.models.device import Device
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, update, and_
except ImportError:
    # Allow module to be imported for testing without full dependencies
    pass

logger = logging.getLogger(__name__)


class RolloutStrategy(Enum):
    """Rollout strategy types for snap distribution"""
    IMMEDIATE = "immediate"
    PROGRESSIVE = "progressive"
    CANARY = "canary"
    SCHEDULED = "scheduled"


class ChannelRisk(Enum):
    """Snap channel risk levels"""
    STABLE = "stable"
    CANDIDATE = "candidate"
    BETA = "beta"
    EDGE = "edge"


@dataclass
class SnapChannel:
    """Snap channel information"""
    track: str = "latest"
    risk: ChannelRisk = ChannelRisk.STABLE
    branch: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        """Get full channel name"""
        channel = f"{self.track}/{self.risk.value}"
        if self.branch:
            channel += f"/{self.branch}"
        return channel


@dataclass
class RolloutPolicy:
    """Progressive rollout policy configuration"""
    strategy: RolloutStrategy
    phases: List[int] = field(default_factory=lambda: [10, 30, 70, 100])
    phase_duration_hours: int = 24
    rollback_threshold_percent: float = 5.0
    health_check_enabled: bool = True
    approval_required: bool = False
    target_groups: Optional[List[str]] = None
    exclude_groups: Optional[List[str]] = None


@dataclass
class SnapDistribution:
    """Snap distribution configuration"""
    snap_name: str
    source_channel: SnapChannel
    target_channel: SnapChannel
    target_devices: List[str]
    rollout_policy: RolloutPolicy
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"


@dataclass
class RolloutStatus:
    """Current rollout status tracking"""
    distribution_id: str
    current_phase: int
    devices_targeted: int
    devices_updated: int
    devices_failed: int
    phase_start_time: datetime
    next_phase_time: Optional[datetime] = None
    status: str = "active"
    errors: List[str] = field(default_factory=list)
    health_metrics: Dict[str, float] = field(default_factory=dict)


class SnapStoreProxyClient:
    """Client for interacting with snap store proxy"""
    
    def __init__(self, proxy_endpoint: str, auth_token: Optional[str] = None):
        self.proxy_endpoint = proxy_endpoint
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def connect(self):
        """Establish connection to snap store proxy"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
            
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            base_url=self.proxy_endpoint
        )
        
        logger.info(f"Connected to snap store proxy at {self.proxy_endpoint}")
        
    async def close(self):
        """Close connection to snap store proxy"""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def configure_device_proxy(self, device_id: str, proxy_config: Dict[str, Any]):
        """Configure device to use snap store proxy"""
        if not self.session:
            raise RuntimeError("Not connected to snap store proxy")
            
        async with self.session.post(f'/api/v1/devices/{device_id}/proxy-config', 
                                   json=proxy_config) as resp:
            if resp.status >= 400:
                error_text = await resp.text()
                raise RuntimeError(f"Proxy configuration failed: {error_text}")
                
            return await resp.json()
            
    async def get_cached_snaps(self) -> List[Dict[str, Any]]:
        """Get list of cached snaps in proxy"""
        if not self.session:
            raise RuntimeError("Not connected to snap store proxy")
            
        async with self.session.get('/api/v1/cache/snaps') as resp:
            if resp.status >= 400:
                error_text = await resp.text()
                raise RuntimeError(f"Failed to get cached snaps: {error_text}")
                
            return await resp.json()
            
    async def pin_snap_revision(self, snap_name: str, channel: str, revision: str):
        """Pin snap revision to specific channel"""
        if not self.session:
            raise RuntimeError("Not connected to snap store proxy")
            
        data = {
            'snap_name': snap_name,
            'channel': channel,
            'revision': revision
        }
        
        async with self.session.post('/api/v1/revisions/pin', json=data) as resp:
            if resp.status >= 400:
                error_text = await resp.text()
                raise RuntimeError(f"Failed to pin revision: {error_text}")
                
            return await resp.json()


class SnapDistributionService:
    """Service for managing enterprise snap distribution"""
    
    def __init__(self):
        self.active_distributions: Dict[str, SnapDistribution] = {}
        self.rollout_status: Dict[str, RolloutStatus] = {}
        self.store_proxy_clients: Dict[str, SnapStoreProxyClient] = {}
        self.running = False
        
    async def start(self):
        """Start the snap distribution service"""
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self._rollout_monitor_task())
        asyncio.create_task(self._health_check_task())
        asyncio.create_task(self._cleanup_task())
        
        logger.info("Snap Distribution Service started")
        
    async def stop(self):
        """Stop the snap distribution service"""
        self.running = False
        
        # Close all proxy connections
        for client in self.store_proxy_clients.values():
            await client.close()
            
        self.store_proxy_clients.clear()
        
        logger.info("Snap Distribution Service stopped")
        
    async def register_store_proxy(self, proxy_id: str, endpoint: str, 
                                 auth_token: Optional[str] = None):
        """Register a snap store proxy for distribution"""
        try:
            client = SnapStoreProxyClient(endpoint, auth_token)
            await client.connect()
            
            # Test connection
            cached_snaps = await client.get_cached_snaps()
            logger.info(f"Store proxy {proxy_id} has {len(cached_snaps)} cached snaps")
            
            self.store_proxy_clients[proxy_id] = client
            
            # Cache proxy info
            cache_key = f"snap_proxy:{proxy_id}"
            proxy_info = {
                'endpoint': endpoint,
                'registered_at': datetime.utcnow().isoformat(),
                'cached_snaps': len(cached_snaps)
            }
            await cache_manager.set(cache_key, json.dumps(proxy_info), ttl=3600)
            
            logger.info(f"Registered snap store proxy: {proxy_id}")
            
        except Exception as e:
            logger.error(f"Failed to register store proxy {proxy_id}: {e}")
            raise
            
    async def create_distribution(self, distribution: SnapDistribution) -> str:
        """Create a new snap distribution"""
        try:
            # Generate unique distribution ID
            distribution_id = hashlib.sha256(
                f"{distribution.snap_name}:{distribution.target_channel.full_name}:"
                f"{len(distribution.target_devices)}:{distribution.created_at}".encode()
            ).hexdigest()[:16]
            
            # Validate target devices exist and are snapd-enabled
            valid_devices = await self._validate_target_devices(distribution.target_devices)
            if not valid_devices:
                raise ValueError("No valid target devices found")
                
            distribution.target_devices = valid_devices
            
            # Store distribution configuration
            self.active_distributions[distribution_id] = distribution
            
            # Initialize rollout status
            rollout_status = RolloutStatus(
                distribution_id=distribution_id,
                current_phase=0,
                devices_targeted=len(valid_devices),
                devices_updated=0,
                devices_failed=0,
                phase_start_time=datetime.utcnow()
            )
            
            # Calculate next phase time for progressive rollouts
            if distribution.rollout_policy.strategy == RolloutStrategy.PROGRESSIVE:
                rollout_status.next_phase_time = (
                    rollout_status.phase_start_time + 
                    timedelta(hours=distribution.rollout_policy.phase_duration_hours)
                )
                
            self.rollout_status[distribution_id] = rollout_status
            
            # Cache distribution info
            cache_key = f"snap_distribution:{distribution_id}"
            dist_data = {
                'snap_name': distribution.snap_name,
                'source_channel': distribution.source_channel.full_name,
                'target_channel': distribution.target_channel.full_name,
                'strategy': distribution.rollout_policy.strategy.value,
                'target_devices': len(distribution.target_devices),
                'created_at': distribution.created_at.isoformat(),
                'created_by': distribution.created_by
            }
            await cache_manager.set(cache_key, json.dumps(dist_data), ttl=86400)
            
            # Start distribution execution
            if distribution.rollout_policy.strategy == RolloutStrategy.IMMEDIATE:
                asyncio.create_task(self._execute_immediate_rollout(distribution_id))
            else:
                asyncio.create_task(self._execute_progressive_rollout(distribution_id))
                
            logger.info(f"Created snap distribution {distribution_id} for {distribution.snap_name}")
            
            # Broadcast distribution created event
            await websocket_manager.broadcast_system_event({
                'type': 'snap_distribution_created',
                'distribution_id': distribution_id,
                'snap_name': distribution.snap_name,
                'strategy': distribution.rollout_policy.strategy.value,
                'target_devices': len(distribution.target_devices),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return distribution_id
            
        except Exception as e:
            logger.error(f"Failed to create distribution for {distribution.snap_name}: {e}")
            raise
            
    async def pause_distribution(self, distribution_id: str):
        """Pause an active distribution"""
        if distribution_id not in self.rollout_status:
            raise ValueError(f"Distribution {distribution_id} not found")
            
        rollout = self.rollout_status[distribution_id]
        rollout.status = "paused"
        
        logger.info(f"Paused distribution {distribution_id}")
        
        # Broadcast pause event
        await websocket_manager.broadcast_system_event({
            'type': 'snap_distribution_paused',
            'distribution_id': distribution_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    async def resume_distribution(self, distribution_id: str):
        """Resume a paused distribution"""
        if distribution_id not in self.rollout_status:
            raise ValueError(f"Distribution {distribution_id} not found")
            
        rollout = self.rollout_status[distribution_id]
        rollout.status = "active"
        
        logger.info(f"Resumed distribution {distribution_id}")
        
        # Broadcast resume event
        await websocket_manager.broadcast_system_event({
            'type': 'snap_distribution_resumed',
            'distribution_id': distribution_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    async def rollback_distribution(self, distribution_id: str):
        """Rollback a distribution to previous version"""
        if distribution_id not in self.active_distributions:
            raise ValueError(f"Distribution {distribution_id} not found")
            
        distribution = self.active_distributions[distribution_id]
        rollout = self.rollout_status[distribution_id]
        
        # Mark as rolling back
        rollout.status = "rolling_back"
        
        try:
            # Get devices that were already updated
            updated_devices = await self._get_updated_devices(distribution_id)
            
            # Revert snap on updated devices
            for device_id in updated_devices:
                try:
                    change_id = await snapd_service.revert_snap_on_device(
                        device_id, distribution.snap_name
                    )
                    
                    # Monitor revert operation
                    asyncio.create_task(
                        self._monitor_rollback_change(distribution_id, device_id, change_id)
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to revert snap on device {device_id}: {e}")
                    rollout.errors.append(f"Rollback failed on {device_id}: {str(e)}")
                    
            rollout.status = "rolled_back"
            
            logger.info(f"Initiated rollback for distribution {distribution_id}")
            
            # Broadcast rollback event
            await websocket_manager.broadcast_system_event({
                'type': 'snap_distribution_rollback',
                'distribution_id': distribution_id,
                'affected_devices': len(updated_devices),
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            rollout.status = "rollback_failed"
            rollout.errors.append(f"Rollback failed: {str(e)}")
            logger.error(f"Failed to rollback distribution {distribution_id}: {e}")
            raise
            
    async def get_distribution_status(self, distribution_id: str) -> Dict[str, Any]:
        """Get current status of a distribution"""
        if distribution_id not in self.rollout_status:
            raise ValueError(f"Distribution {distribution_id} not found")
            
        distribution = self.active_distributions.get(distribution_id)
        rollout = self.rollout_status[distribution_id]
        
        return {
            'distribution_id': distribution_id,
            'snap_name': distribution.snap_name if distribution else 'unknown',
            'current_phase': rollout.current_phase,
            'total_phases': len(distribution.rollout_policy.phases) if distribution else 0,
            'devices_targeted': rollout.devices_targeted,
            'devices_updated': rollout.devices_updated,
            'devices_failed': rollout.devices_failed,
            'progress_percent': (rollout.devices_updated / rollout.devices_targeted * 100) 
                              if rollout.devices_targeted > 0 else 0,
            'status': rollout.status,
            'phase_start_time': rollout.phase_start_time.isoformat(),
            'next_phase_time': rollout.next_phase_time.isoformat() if rollout.next_phase_time else None,
            'errors': rollout.errors,
            'health_metrics': rollout.health_metrics
        }
        
    async def list_active_distributions(self) -> List[Dict[str, Any]]:
        """List all active distributions"""
        distributions = []
        
        for distribution_id in self.active_distributions:
            try:
                status = await self.get_distribution_status(distribution_id)
                distributions.append(status)
            except Exception as e:
                logger.error(f"Error getting status for distribution {distribution_id}: {e}")
                
        return distributions
        
    async def _validate_target_devices(self, device_ids: List[str]) -> List[str]:
        """Validate that target devices exist and are snapd-enabled"""
        valid_devices = []
        
        # This would query the database to check device status
        # For now, we'll assume all devices are valid
        # In a real implementation, this would check:
        # - Device exists in database
        # - Device is online/reachable
        # - Device has snapd enabled
        # - Device is in correct device groups
        
        for device_id in device_ids:
            # Simulate device validation
            try:
                # Check if device is registered for snapd management
                connection = await snapd_service.get_connection(device_id)
                if connection:
                    valid_devices.append(device_id)
            except Exception as e:
                logger.warning(f"Device {device_id} not valid for snap distribution: {e}")
                
        return valid_devices
        
    async def _execute_immediate_rollout(self, distribution_id: str):
        """Execute immediate rollout to all target devices"""
        try:
            distribution = self.active_distributions[distribution_id]
            rollout = self.rollout_status[distribution_id]
            
            # Update all devices immediately
            for device_id in distribution.target_devices:
                try:
                    if distribution.source_channel != distribution.target_channel:
                        # Install from target channel
                        change_id = await snapd_service.install_snap_on_device(
                            device_id, 
                            distribution.snap_name,
                            channel=distribution.target_channel.full_name
                        )
                    else:
                        # Refresh existing snap
                        change_id = await snapd_service.refresh_snap_on_device(
                            device_id, 
                            distribution.snap_name,
                            channel=distribution.target_channel.full_name
                        )
                        
                    # Monitor the change
                    asyncio.create_task(
                        self._monitor_distribution_change(distribution_id, device_id, change_id)
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to update snap on device {device_id}: {e}")
                    rollout.devices_failed += 1
                    rollout.errors.append(f"Update failed on {device_id}: {str(e)}")
                    
            rollout.status = "completed"
            
        except Exception as e:
            logger.error(f"Failed to execute immediate rollout {distribution_id}: {e}")
            self.rollout_status[distribution_id].status = "failed"
            
    async def _execute_progressive_rollout(self, distribution_id: str):
        """Execute progressive rollout with controlled phases"""
        try:
            distribution = self.active_distributions[distribution_id]
            rollout = self.rollout_status[distribution_id]
            
            # Calculate device groups for each phase
            phase_percentages = distribution.rollout_policy.phases
            total_devices = len(distribution.target_devices)
            
            for phase_idx, percentage in enumerate(phase_percentages):
                if rollout.status in ["paused", "cancelled", "failed"]:
                    break
                    
                rollout.current_phase = phase_idx
                rollout.phase_start_time = datetime.utcnow()
                
                # Calculate devices for this phase
                devices_for_phase = int(total_devices * percentage / 100)
                start_idx = sum(int(total_devices * p / 100) for p in phase_percentages[:phase_idx])
                end_idx = start_idx + devices_for_phase
                
                phase_devices = distribution.target_devices[start_idx:end_idx]
                
                logger.info(f"Starting phase {phase_idx + 1} of distribution {distribution_id}, "
                          f"targeting {len(phase_devices)} devices ({percentage}%)")
                
                # Update devices in this phase
                phase_success = 0
                phase_failures = 0
                
                for device_id in phase_devices:
                    try:
                        if distribution.source_channel != distribution.target_channel:
                            change_id = await snapd_service.install_snap_on_device(
                                device_id,
                                distribution.snap_name,
                                channel=distribution.target_channel.full_name
                            )
                        else:
                            change_id = await snapd_service.refresh_snap_on_device(
                                device_id,
                                distribution.snap_name,
                                channel=distribution.target_channel.full_name
                            )
                            
                        # Monitor the change
                        asyncio.create_task(
                            self._monitor_distribution_change(distribution_id, device_id, change_id)
                        )
                        
                        phase_success += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to update snap on device {device_id}: {e}")
                        phase_failures += 1
                        rollout.errors.append(f"Update failed on {device_id}: {str(e)}")
                        
                # Check if we should continue to next phase
                failure_rate = phase_failures / len(phase_devices) * 100 if phase_devices else 0
                
                if failure_rate > distribution.rollout_policy.rollback_threshold_percent:
                    logger.warning(f"Phase {phase_idx + 1} failure rate {failure_rate:.1f}% exceeds "
                                 f"threshold {distribution.rollout_policy.rollback_threshold_percent}%")
                    
                    if distribution.rollout_policy.approval_required:
                        rollout.status = "awaiting_approval"
                        break
                    else:
                        # Automatic rollback
                        await self.rollback_distribution(distribution_id)
                        return
                        
                # Wait for phase duration before next phase (except last phase)
                if phase_idx < len(phase_percentages) - 1:
                    rollout.next_phase_time = (
                        datetime.utcnow() + 
                        timedelta(hours=distribution.rollout_policy.phase_duration_hours)
                    )
                    
                    # Wait for phase duration or status change
                    wait_time = distribution.rollout_policy.phase_duration_hours * 3600
                    await asyncio.sleep(wait_time)
                    
            if rollout.status == "active":
                rollout.status = "completed"
                
        except Exception as e:
            logger.error(f"Failed to execute progressive rollout {distribution_id}: {e}")
            self.rollout_status[distribution_id].status = "failed"
            
    async def _monitor_distribution_change(self, distribution_id: str, 
                                         device_id: str, change_id: str):
        """Monitor a snap change for distribution tracking"""
        try:
            connection = await snapd_service.get_connection(device_id)
            success = await connection.wait_for_change(change_id, timeout=1800)
            
            rollout = self.rollout_status[distribution_id]
            
            if success:
                rollout.devices_updated += 1
                logger.info(f"Successfully updated snap on device {device_id} "
                          f"for distribution {distribution_id}")
            else:
                rollout.devices_failed += 1
                change = await connection.get_change(change_id)
                error_msg = f"Update failed on {device_id}: {change.err}"
                rollout.errors.append(error_msg)
                logger.error(error_msg)
                
        except Exception as e:
            logger.error(f"Error monitoring change {change_id} for device {device_id}: {e}")
            self.rollout_status[distribution_id].devices_failed += 1
            
    async def _monitor_rollback_change(self, distribution_id: str, 
                                     device_id: str, change_id: str):
        """Monitor a rollback change operation"""
        try:
            connection = await snapd_service.get_connection(device_id)
            success = await connection.wait_for_change(change_id, timeout=1800)
            
            if success:
                logger.info(f"Successfully rolled back snap on device {device_id} "
                          f"for distribution {distribution_id}")
            else:
                change = await connection.get_change(change_id)
                error_msg = f"Rollback failed on {device_id}: {change.err}"
                self.rollout_status[distribution_id].errors.append(error_msg)
                logger.error(error_msg)
                
        except Exception as e:
            logger.error(f"Error monitoring rollback change {change_id} for device {device_id}: {e}")
            
    async def _get_updated_devices(self, distribution_id: str) -> List[str]:
        """Get list of devices that were successfully updated in a distribution"""
        # This would track which devices were successfully updated
        # For now, return empty list as placeholder
        return []
        
    async def _rollout_monitor_task(self):
        """Background task to monitor active rollouts"""
        while self.running:
            try:
                for distribution_id, rollout in self.rollout_status.items():
                    if rollout.status == "active" and rollout.next_phase_time:
                        if datetime.utcnow() >= rollout.next_phase_time:
                            # Time for next phase
                            distribution = self.active_distributions.get(distribution_id)
                            if distribution and distribution.rollout_policy.strategy == RolloutStrategy.PROGRESSIVE:
                                # Continue progressive rollout
                                asyncio.create_task(self._execute_progressive_rollout(distribution_id))
                                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in rollout monitor task: {e}")
                await asyncio.sleep(60)
                
    async def _health_check_task(self):
        """Background task to perform health checks on distributed snaps"""
        while self.running:
            try:
                # Perform health checks on completed distributions
                for distribution_id, rollout in self.rollout_status.items():
                    if rollout.status == "completed":
                        await self._check_distribution_health(distribution_id)
                        
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in health check task: {e}")
                await asyncio.sleep(60)
                
    async def _check_distribution_health(self, distribution_id: str):
        """Check health of snaps in a completed distribution"""
        try:
            distribution = self.active_distributions.get(distribution_id)
            if not distribution:
                return
                
            rollout = self.rollout_status[distribution_id]
            healthy_devices = 0
            total_checked = 0
            
            for device_id in distribution.target_devices:
                try:
                    # Get current snap info
                    snap_info = await snapd_service.get_device_snap_info(
                        device_id, distribution.snap_name
                    )
                    
                    # Check if snap is in expected state
                    if snap_info.status == "active" and snap_info.channel == distribution.target_channel.full_name:
                        healthy_devices += 1
                        
                    total_checked += 1
                    
                except Exception as e:
                    logger.warning(f"Health check failed for device {device_id}: {e}")
                    
            # Update health metrics
            if total_checked > 0:
                health_percentage = (healthy_devices / total_checked) * 100
                rollout.health_metrics['health_percentage'] = health_percentage
                rollout.health_metrics['last_check'] = datetime.utcnow().isoformat()
                
                logger.debug(f"Distribution {distribution_id} health: {health_percentage:.1f}% "
                           f"({healthy_devices}/{total_checked})")
                
        except Exception as e:
            logger.error(f"Error checking health for distribution {distribution_id}: {e}")
            
    async def _cleanup_task(self):
        """Background task to clean up completed distributions"""
        while self.running:
            try:
                # Clean up distributions older than 7 days
                cutoff_time = datetime.utcnow() - timedelta(days=7)
                
                expired_distributions = []
                for distribution_id, distribution in self.active_distributions.items():
                    if distribution.created_at < cutoff_time:
                        rollout = self.rollout_status.get(distribution_id)
                        if rollout and rollout.status in ["completed", "failed", "cancelled"]:
                            expired_distributions.append(distribution_id)
                            
                for distribution_id in expired_distributions:
                    del self.active_distributions[distribution_id]
                    del self.rollout_status[distribution_id]
                    
                    # Clear cache
                    cache_key = f"snap_distribution:{distribution_id}"
                    await cache_manager.delete(cache_key)
                    
                    logger.info(f"Cleaned up expired distribution {distribution_id}")
                    
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)


# Global service instance
snap_distribution_service = SnapDistributionService()