#!/usr/bin/env python3
"""
Update Manager for AI Worker Node
Handles snap updates with AI workload awareness
"""

import os
import json
import asyncio
import logging
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import subprocess
import time

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class WorkloadStatus(Enum):
    IDLE = "idle"
    TRAINING = "training"
    INFERENCE = "inference"
    MAINTENANCE = "maintenance"


@dataclass
class UpdatePolicy:
    """Update policy configuration"""
    auto_update_enabled: bool = True
    update_window_start: str = "02:00"
    update_window_end: str = "06:00"
    max_gpu_utilization: float = 10.0  # Max GPU usage % to allow updates
    min_idle_time: int = 300  # Minimum idle time in seconds before update
    enable_canary_updates: bool = True
    rollback_on_failure: bool = True
    update_check_interval: int = 3600  # Check for updates every hour
    defer_during_training: bool = True


@dataclass
class UpdateInfo:
    """Information about available updates"""
    snap_name: str
    current_revision: str
    available_revision: str
    channel: str
    size_bytes: int
    update_status: UpdateStatus
    scheduled_time: Optional[datetime] = None
    error_message: Optional[str] = None


class WorkloadMonitor:
    """Monitors AI workload status to determine update timing"""
    
    def __init__(self):
        self.ray_available = self._check_ray_availability()
        
    def _check_ray_availability(self) -> bool:
        """Check if Ray is available"""
        try:
            import ray
            return True
        except ImportError:
            logger.warning("Ray not available for workload monitoring")
            return False
            
    async def get_workload_status(self) -> WorkloadStatus:
        """Get current workload status"""
        try:
            # Check GPU utilization
            gpu_util = await self._get_gpu_utilization()
            if gpu_util > 50:
                return WorkloadStatus.TRAINING
            elif gpu_util > 10:
                return WorkloadStatus.INFERENCE
                
            # Check Ray cluster status
            if self.ray_available:
                ray_status = await self._get_ray_status()
                if ray_status.get('active_tasks', 0) > 0:
                    return WorkloadStatus.TRAINING
                elif ray_status.get('running_actors', 0) > 0:
                    return WorkloadStatus.INFERENCE
                    
            return WorkloadStatus.IDLE
            
        except Exception as e:
            logger.error(f"Error checking workload status: {e}")
            return WorkloadStatus.MAINTENANCE
            
    async def _get_gpu_utilization(self) -> float:
        """Get current GPU utilization percentage"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Get highest utilization across all GPUs
                utils = [float(x.strip()) for x in result.stdout.strip().split('\n') if x.strip()]
                return max(utils) if utils else 0.0
                
        except Exception as e:
            logger.debug(f"Error getting GPU utilization: {e}")
            
        return 0.0
        
    async def _get_ray_status(self) -> Dict[str, Any]:
        """Get Ray cluster status"""
        try:
            if not self.ray_available:
                return {}
                
            import ray
            if not ray.is_initialized():
                return {}
                
            # Get cluster resources and usage
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            # Estimate active tasks (simplified)
            cpu_used = cluster_resources.get('CPU', 0) - available_resources.get('CPU', 0)
            
            return {
                'active_tasks': max(0, int(cpu_used)),
                'running_actors': len(ray.state.actors()),
                'cluster_resources': cluster_resources,
                'available_resources': available_resources
            }
            
        except Exception as e:
            logger.debug(f"Error getting Ray status: {e}")
            return {}
            
    async def wait_for_idle(self, timeout: int = 3600) -> bool:
        """Wait for workload to become idle"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = await self.get_workload_status()
            if status == WorkloadStatus.IDLE:
                return True
                
            logger.info(f"Waiting for workload to become idle, current status: {status.value}")
            await asyncio.sleep(30)  # Check every 30 seconds
            
        return False


class SnapUpdateManager:
    """Manages snap updates with snapd REST API"""
    
    def __init__(self):
        self.socket_path = "/run/snapd.socket"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        """Initialize the update manager"""
        # Create Unix socket connector
        connector = aiohttp.UnixConnector(path=self.socket_path)
        self.session = aiohttp.ClientSession(connector=connector)
        
    async def stop(self):
        """Cleanup the update manager"""
        if self.session:
            await self.session.close()
            
    async def get_installed_snaps(self) -> List[Dict[str, Any]]:
        """Get list of installed snaps"""
        if not self.session:
            raise RuntimeError("Update manager not started")
            
        async with self.session.get("http://snapd/v2/snaps") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('result', [])
            else:
                raise Exception(f"Failed to get installed snaps: {resp.status}")
                
    async def check_for_updates(self, snap_names: List[str]) -> List[UpdateInfo]:
        """Check for available updates"""
        updates = []
        
        for snap_name in snap_names:
            try:
                # Get current snap info
                async with self.session.get(f"http://snapd/v2/snaps/{snap_name}") as resp:
                    if resp.status != 200:
                        continue
                        
                    snap_data = await resp.json()
                    current_snap = snap_data['result']
                    
                # Check for updates using find API
                params = {
                    'name': snap_name,
                    'channel': current_snap.get('channel', 'stable')
                }
                
                async with self.session.get("http://snapd/v2/find", params=params) as resp:
                    if resp.status == 200:
                        find_data = await resp.json()
                        results = find_data.get('result', [])
                        
                        if results:
                            latest_snap = results[0]
                            current_rev = current_snap.get('revision', '')
                            latest_rev = latest_snap.get('revision', '')
                            
                            if current_rev != latest_rev:
                                update_info = UpdateInfo(
                                    snap_name=snap_name,
                                    current_revision=current_rev,
                                    available_revision=latest_rev,
                                    channel=current_snap.get('channel', 'stable'),
                                    size_bytes=latest_snap.get('download-size', 0),
                                    update_status=UpdateStatus.PENDING
                                )
                                updates.append(update_info)
                                
            except Exception as e:
                logger.error(f"Error checking updates for {snap_name}: {e}")
                
        return updates
        
    async def refresh_snap(self, snap_name: str, channel: Optional[str] = None) -> str:
        """Refresh a snap and return change ID"""
        if not self.session:
            raise RuntimeError("Update manager not started")
            
        data = {
            "action": "refresh"
        }
        
        if channel:
            data["channel"] = channel
            
        async with self.session.post(
            f"http://snapd/v2/snaps/{snap_name}",
            json=data
        ) as resp:
            if resp.status == 202:  # Accepted
                response_data = await resp.json()
                return response_data['change']
            else:
                error_text = await resp.text()
                raise Exception(f"Failed to refresh snap {snap_name}: {error_text}")
                
    async def get_change_status(self, change_id: str) -> Dict[str, Any]:
        """Get status of a change operation"""
        if not self.session:
            raise RuntimeError("Update manager not started")
            
        async with self.session.get(f"http://snapd/v2/changes/{change_id}") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['result']
            else:
                raise Exception(f"Failed to get change status: {resp.status}")
                
    async def wait_for_change_completion(self, change_id: str, timeout: int = 1800) -> bool:
        """Wait for a change to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                change_status = await self.get_change_status(change_id)
                status = change_status.get('status')
                
                if status == 'Done':
                    return True
                elif status in ['Error', 'Hold']:
                    logger.error(f"Change {change_id} failed with status: {status}")
                    return False
                    
                # Still in progress
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error waiting for change completion: {e}")
                await asyncio.sleep(10)
                
        logger.error(f"Change {change_id} timed out after {timeout} seconds")
        return False
        
    async def revert_snap(self, snap_name: str) -> str:
        """Revert a snap to previous revision"""
        if not self.session:
            raise RuntimeError("Update manager not started")
            
        data = {
            "action": "revert"
        }
        
        async with self.session.post(
            f"http://snapd/v2/snaps/{snap_name}",
            json=data
        ) as resp:
            if resp.status == 202:
                response_data = await resp.json()
                return response_data['change']
            else:
                error_text = await resp.text()
                raise Exception(f"Failed to revert snap {snap_name}: {error_text}")


class AIWorkerUpdateManager:
    """Main update manager for AI worker nodes"""
    
    def __init__(self, management_url: str, node_id: str):
        self.management_url = management_url
        self.node_id = node_id
        self.policy = UpdatePolicy()
        self.workload_monitor = WorkloadMonitor()
        self.snap_manager = SnapUpdateManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        
        # Load configuration
        self._load_config()
        
    def _load_config(self):
        """Load update configuration"""
        config_file = os.path.join(
            os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current'),
            'update-policy.json'
        )
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    
                # Update policy with loaded configuration
                for key, value in config_data.items():
                    if hasattr(self.policy, key):
                        setattr(self.policy, key, value)
                        
            except Exception as e:
                logger.error(f"Failed to load update policy: {e}")
                
    async def start(self):
        """Start the update manager"""
        self.session = aiohttp.ClientSession()
        await self.snap_manager.start()
        self.running = True
        
        logger.info("AI Worker Update Manager started")
        
        # Start main update loop
        if self.policy.auto_update_enabled:
            asyncio.create_task(self._update_loop())
            
    async def stop(self):
        """Stop the update manager"""
        self.running = False
        
        if self.session:
            await self.session.close()
            
        await self.snap_manager.stop()
        logger.info("AI Worker Update Manager stopped")
        
    async def _update_loop(self):
        """Main update checking and processing loop"""
        while self.running:
            try:
                await self._check_and_process_updates()
                await asyncio.sleep(self.policy.update_check_interval)
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
                
    async def _check_and_process_updates(self):
        """Check for and process available updates"""
        # Get AI worker related snaps
        ai_snaps = ['ai-worker', 'ray-head', 'network-manager-server']
        
        # Check for available updates
        updates = await self.snap_manager.check_for_updates(ai_snaps)
        
        if not updates:
            logger.debug("No updates available")
            return
            
        logger.info(f"Found {len(updates)} available updates")
        
        # Check if we're in update window
        if not self._is_in_update_window():
            logger.info("Outside update window, deferring updates")
            return
            
        # Check workload status
        workload_status = await self.workload_monitor.get_workload_status()
        
        if (self.policy.defer_during_training and 
            workload_status in [WorkloadStatus.TRAINING, WorkloadStatus.INFERENCE]):
            logger.info(f"Workload active ({workload_status.value}), deferring updates")
            return
            
        # Process updates
        for update in updates:
            await self._process_update(update)
            
    def _is_in_update_window(self) -> bool:
        """Check if current time is within update window"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Simple time range check (assumes same day)
        return (self.policy.update_window_start <= current_time <= 
                self.policy.update_window_end)
                
    async def _process_update(self, update: UpdateInfo):
        """Process a single update"""
        try:
            logger.info(f"Processing update for {update.snap_name}")
            
            # Report update start
            await self._report_update_status(update, UpdateStatus.DOWNLOADING)
            
            # Wait for workload to be idle if needed
            if self.policy.defer_during_training:
                idle_achieved = await self.workload_monitor.wait_for_idle(
                    timeout=self.policy.min_idle_time
                )
                
                if not idle_achieved:
                    logger.warning(f"Could not achieve idle state for {update.snap_name}")
                    update.error_message = "Workload did not become idle within timeout"
                    await self._report_update_status(update, UpdateStatus.FAILED)
                    return
                    
            # Perform the update
            update.update_status = UpdateStatus.INSTALLING
            await self._report_update_status(update, UpdateStatus.INSTALLING)
            
            change_id = await self.snap_manager.refresh_snap(
                update.snap_name, 
                update.channel
            )
            
            # Wait for completion
            success = await self.snap_manager.wait_for_change_completion(change_id)
            
            if success:
                update.update_status = UpdateStatus.COMPLETED
                logger.info(f"Successfully updated {update.snap_name}")
                
                # Perform post-update health check
                if not await self._health_check(update.snap_name):
                    logger.error(f"Health check failed for {update.snap_name}")
                    
                    if self.policy.rollback_on_failure:
                        await self._rollback_update(update)
                        return
                        
            else:
                update.update_status = UpdateStatus.FAILED
                update.error_message = "Update installation failed"
                logger.error(f"Failed to update {update.snap_name}")
                
            await self._report_update_status(update, update.update_status)
            
        except Exception as e:
            logger.error(f"Error processing update for {update.snap_name}: {e}")
            update.update_status = UpdateStatus.FAILED
            update.error_message = str(e)
            await self._report_update_status(update, UpdateStatus.FAILED)
            
    async def _health_check(self, snap_name: str) -> bool:
        """Perform health check after update"""
        try:
            # Wait a bit for services to start
            await asyncio.sleep(30)
            
            if snap_name == 'ai-worker':
                # Check if Ray worker is healthy
                workload_status = await self.workload_monitor.get_workload_status()
                return workload_status != WorkloadStatus.MAINTENANCE
                
            elif snap_name == 'ray-head':
                # Check if Ray head is accessible
                # This could include checking Ray dashboard or API
                return True  # Simplified for now
                
            elif snap_name == 'network-manager-server':
                # Check if management API is responding
                try:
                    if self.session:
                        async with self.session.get(
                            f"{self.management_url}/health",
                            timeout=10
                        ) as resp:
                            return resp.status == 200
                except:
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Health check failed for {snap_name}: {e}")
            return False
            
    async def _rollback_update(self, update: UpdateInfo):
        """Rollback a failed update"""
        try:
            logger.info(f"Rolling back update for {update.snap_name}")
            
            change_id = await self.snap_manager.revert_snap(update.snap_name)
            success = await self.snap_manager.wait_for_change_completion(change_id)
            
            if success:
                update.update_status = UpdateStatus.ROLLED_BACK
                logger.info(f"Successfully rolled back {update.snap_name}")
            else:
                logger.error(f"Failed to rollback {update.snap_name}")
                
            await self._report_update_status(update, update.update_status)
            
        except Exception as e:
            logger.error(f"Error rolling back {update.snap_name}: {e}")
            
    async def _report_update_status(self, update: UpdateInfo, status: UpdateStatus):
        """Report update status to management platform"""
        if not self.session:
            return
            
        try:
            data = {
                'node_id': self.node_id,
                'update_info': asdict(update),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            async with self.session.post(
                f"{self.management_url}/api/v1/updates/status",
                json=data,
                timeout=10
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to report update status: {resp.status}")
                    
        except Exception as e:
            logger.debug(f"Error reporting update status: {e}")


async def main():
    """Test the update manager"""
    logging.basicConfig(level=logging.INFO)
    
    manager = AIWorkerUpdateManager(
        management_url="http://localhost:8000",
        node_id="test-node"
    )
    
    await manager.start()
    
    try:
        # Run for a while
        await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())