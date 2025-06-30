"""
Update Manager Service
Manages snap updates across the AI worker fleet
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import aiohttp

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager
from app.schemas.updates import UpdateStatus, RolloutStrategy

logger = logging.getLogger(__name__)


@dataclass
class FleetUpdate:
    """Fleet update tracking"""
    update_id: str
    node_ids: List[str]
    snap_names: List[str]
    rollout_strategy: RolloutStrategy
    canary_percentage: int
    batch_size: int
    delay_between_batches: int
    max_failures: int
    status: str
    created_at: datetime
    completed_nodes: List[str]
    failed_nodes: List[str]
    pending_nodes: List[str]
    current_batch: int
    total_batches: int


class UpdateManagerService:
    """Service for managing snap updates across AI worker fleet"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.fleet_updates: Dict[str, FleetUpdate] = {}
        self.node_statuses: Dict[str, Dict[str, Any]] = {}
        self.running = False
        
    async def start(self):
        """Start the update manager service"""
        self.session = aiohttp.ClientSession()
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self._fleet_update_monitor())
        asyncio.create_task(self._node_status_sync())
        
        logger.info("Update Manager Service started")
        
    async def stop(self):
        """Stop the update manager service"""
        self.running = False
        
        if self.session:
            await self.session.close()
            
        logger.info("Update Manager Service stopped")
        
    async def get_node_status(self, node_id: str) -> Dict[str, Any]:
        """Get update status for a specific node"""
        try:
            # Try to get cached status first
            cache_key = f"node_status:{node_id}"
            cached_status = await cache_manager.get(cache_key)
            
            if cached_status:
                return json.loads(cached_status)
                
            # Fetch fresh status from node
            status = await self._fetch_node_status(node_id)
            
            # Cache the result
            await cache_manager.set(cache_key, json.dumps(status), ttl=300)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting node status for {node_id}: {e}")
            return {
                "node_id": node_id,
                "current_status": UpdateStatus.FAILED.value,
                "error_message": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
            
    async def get_all_nodes_status(self) -> List[Dict[str, Any]]:
        """Get update status for all nodes"""
        try:
            # Get list of known nodes from database or cache
            node_ids = await self._get_known_node_ids()
            
            # Fetch status for all nodes concurrently
            tasks = [self.get_node_status(node_id) for node_id in node_ids]
            statuses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and return valid statuses
            valid_statuses = []
            for status in statuses:
                if isinstance(status, dict):
                    valid_statuses.append(status)
                    
            return valid_statuses
            
        except Exception as e:
            logger.error(f"Error getting all nodes status: {e}")
            return []
            
    async def trigger_update_check(self, node_id: str) -> Dict[str, Any]:
        """Trigger update check for a specific node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.post(
                f"{node_url}/api/v1/updates/check",
                timeout=30
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Clear cached status to force refresh
                    cache_key = f"node_status:{node_id}"
                    await cache_manager.delete(cache_key)
                    
                    return result
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error triggering update check for {node_id}: {e}")
            raise
            
    async def install_updates(self, node_id: str, snap_names: List[str], 
                            force: bool = False, channel: Optional[str] = None) -> Dict[str, Any]:
        """Install updates on a specific node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            data = {
                "snap_names": snap_names,
                "force": force
            }
            
            if channel:
                data["channel"] = channel
                
            async with self.session.post(
                f"{node_url}/api/v1/updates/install",
                json=data,
                timeout=1800  # 30 minutes timeout for updates
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Update node status cache
                    await self._update_node_status_cache(node_id, {
                        "current_status": UpdateStatus.INSTALLING.value,
                        "installing_snaps": snap_names,
                        "last_update_start": datetime.utcnow().isoformat()
                    })
                    
                    return result
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error installing updates on {node_id}: {e}")
            raise
            
    async def rollback_snap(self, node_id: str, snap_name: str) -> Dict[str, Any]:
        """Rollback a snap to previous revision"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.post(
                f"{node_url}/api/v1/updates/rollback",
                json={"snap_name": snap_name},
                timeout=600  # 10 minutes timeout
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Update node status cache
                    await self._update_node_status_cache(node_id, {
                        "last_rollback": datetime.utcnow().isoformat(),
                        "rolled_back_snap": snap_name
                    })
                    
                    return result
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error rolling back {snap_name} on {node_id}: {e}")
            raise
            
    async def start_fleet_update(self, node_ids: List[str], snap_names: List[str],
                                rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY,
                                canary_percentage: int = 10, batch_size: int = 10,
                                delay_between_batches: int = 300, max_failures: int = 5) -> Dict[str, Any]:
        """Start a fleet-wide update"""
        try:
            update_id = str(uuid.uuid4())
            
            # Calculate batches
            if rollout_strategy == RolloutStrategy.CANARY:
                canary_count = max(1, len(node_ids) * canary_percentage // 100)
                canary_nodes = node_ids[:canary_count]
                remaining_nodes = node_ids[canary_count:]
                
                # Calculate total batches (canary + remaining batches)
                total_batches = 1 + (len(remaining_nodes) + batch_size - 1) // batch_size
            else:
                total_batches = (len(node_ids) + batch_size - 1) // batch_size
                
            # Create fleet update tracking
            fleet_update = FleetUpdate(
                update_id=update_id,
                node_ids=node_ids.copy(),
                snap_names=snap_names.copy(),
                rollout_strategy=rollout_strategy,
                canary_percentage=canary_percentage,
                batch_size=batch_size,
                delay_between_batches=delay_between_batches,
                max_failures=max_failures,
                status="running",
                created_at=datetime.utcnow(),
                completed_nodes=[],
                failed_nodes=[],
                pending_nodes=node_ids.copy(),
                current_batch=0,
                total_batches=total_batches
            )
            
            self.fleet_updates[update_id] = fleet_update
            
            # Start the fleet update process
            asyncio.create_task(self._execute_fleet_update(fleet_update))
            
            return {
                "update_id": update_id,
                "total_nodes": len(node_ids),
                "rollout_strategy": rollout_strategy.value,
                "status": "running",
                "created_at": fleet_update.created_at
            }
            
        except Exception as e:
            logger.error(f"Error starting fleet update: {e}")
            raise
            
    async def get_fleet_update_status(self, update_id: str) -> Dict[str, Any]:
        """Get status of a fleet update"""
        if update_id not in self.fleet_updates:
            raise ValueError(f"Fleet update {update_id} not found")
            
        fleet_update = self.fleet_updates[update_id]
        
        return {
            "update_id": update_id,
            "rollout_strategy": fleet_update.rollout_strategy.value,
            "total_nodes": len(fleet_update.node_ids),
            "completed_nodes": len(fleet_update.completed_nodes),
            "failed_nodes": len(fleet_update.failed_nodes),
            "pending_nodes": len(fleet_update.pending_nodes),
            "current_batch": fleet_update.current_batch,
            "total_batches": fleet_update.total_batches,
            "status": fleet_update.status,
            "started_at": fleet_update.created_at,
            "estimated_completion": self._estimate_completion_time(fleet_update)
        }
        
    async def cancel_fleet_update(self, update_id: str) -> Dict[str, Any]:
        """Cancel a running fleet update"""
        if update_id not in self.fleet_updates:
            raise ValueError(f"Fleet update {update_id} not found")
            
        fleet_update = self.fleet_updates[update_id]
        fleet_update.status = "cancelled"
        
        logger.info(f"Fleet update {update_id} cancelled")
        
        return {"cancelled": True, "remaining_nodes": len(fleet_update.pending_nodes)}
        
    async def get_update_policy(self, node_id: str) -> Dict[str, Any]:
        """Get update policy for a node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.get(
                f"{node_url}/api/v1/updates/policy",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error getting update policy for {node_id}: {e}")
            raise
            
    async def update_policy(self, node_id: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Update policy for a node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.put(
                f"{node_url}/api/v1/updates/policy",
                json=policy,
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error updating policy for {node_id}: {e}")
            raise
            
    async def get_update_schedule(self, node_id: str) -> Dict[str, Any]:
        """Get update schedule for a node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.get(
                f"{node_url}/api/v1/updates/schedule",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error getting update schedule for {node_id}: {e}")
            raise
            
    async def update_schedule(self, node_id: str, schedule: Dict[str, Any]) -> Dict[str, Any]:
        """Update schedule for a node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.put(
                f"{node_url}/api/v1/updates/schedule",
                json=schedule,
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error updating schedule for {node_id}: {e}")
            raise
            
    async def get_update_history(self, node_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get update history for a node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            params = {"limit": limit, "offset": offset}
            
            async with self.session.get(
                f"{node_url}/api/v1/updates/history",
                params=params,
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("history", [])
                else:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error getting update history for {node_id}: {e}")
            return []
            
    async def process_status_report(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process status report from a node"""
        try:
            node_id = status_data.get("node_id")
            if not node_id:
                raise ValueError("Missing node_id in status report")
                
            # Update cached status
            await self._update_node_status_cache(node_id, status_data)
            
            # Check if this affects any fleet updates
            await self._check_fleet_update_progress(node_id, status_data)
            
            return {"processed": True}
            
        except Exception as e:
            logger.error(f"Error processing status report: {e}")
            raise
            
    async def emergency_stop_all_updates(self) -> Dict[str, Any]:
        """Emergency stop all running updates"""
        try:
            stopped_count = 0
            
            # Cancel all fleet updates
            for update_id, fleet_update in self.fleet_updates.items():
                if fleet_update.status == "running":
                    fleet_update.status = "emergency_stopped"
                    stopped_count += 1
                    
            # Send stop commands to all nodes
            node_ids = await self._get_known_node_ids()
            tasks = []
            
            for node_id in node_ids:
                tasks.append(self._send_emergency_stop(node_id))
                
            # Wait for all stop commands (with timeout)
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30)
            except asyncio.TimeoutError:
                logger.warning("Some emergency stop commands timed out")
                
            logger.warning(f"Emergency stop triggered - stopped {stopped_count} fleet updates")
            
            return {"stopped_fleet_updates": stopped_count, "stop_commands_sent": len(node_ids)}
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            raise
            
    # Private methods
    
    async def _fetch_node_status(self, node_id: str) -> Dict[str, Any]:
        """Fetch status from a specific node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                raise RuntimeError("Update manager not started")
                
            async with self.session.get(
                f"{node_url}/api/v1/updates/status",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}")
                    
        except Exception as e:
            logger.debug(f"Error fetching status from {node_id}: {e}")
            raise
            
    async def _get_node_url(self, node_id: str) -> str:
        """Get the URL for a specific node"""
        # This would typically look up node IPs from database
        # For now, assume nodes are accessible via predictable URLs
        return f"http://{node_id}:8000"
        
    async def _get_known_node_ids(self) -> List[str]:
        """Get list of known node IDs"""
        # This would typically query the database for registered nodes
        # For now, return cached node IDs
        return list(self.node_statuses.keys())
        
    async def _update_node_status_cache(self, node_id: str, status_update: Dict[str, Any]):
        """Update cached node status"""
        cache_key = f"node_status:{node_id}"
        
        # Get existing status
        existing_status = await cache_manager.get(cache_key)
        if existing_status:
            status = json.loads(existing_status)
        else:
            status = {"node_id": node_id}
            
        # Update with new data
        status.update(status_update)
        status["last_updated"] = datetime.utcnow().isoformat()
        
        # Cache updated status
        await cache_manager.set(cache_key, json.dumps(status), ttl=3600)
        
    async def _execute_fleet_update(self, fleet_update: FleetUpdate):
        """Execute a fleet update"""
        try:
            if fleet_update.rollout_strategy == RolloutStrategy.CANARY:
                await self._execute_canary_rollout(fleet_update)
            elif fleet_update.rollout_strategy == RolloutStrategy.STAGED:
                await self._execute_staged_rollout(fleet_update)
            else:
                await self._execute_immediate_rollout(fleet_update)
                
        except Exception as e:
            logger.error(f"Error executing fleet update {fleet_update.update_id}: {e}")
            fleet_update.status = "failed"
            
    async def _execute_canary_rollout(self, fleet_update: FleetUpdate):
        """Execute canary rollout strategy"""
        try:
            # Phase 1: Canary deployment
            canary_count = max(1, len(fleet_update.node_ids) * fleet_update.canary_percentage // 100)
            canary_nodes = fleet_update.node_ids[:canary_count]
            
            logger.info(f"Starting canary deployment for {len(canary_nodes)} nodes")
            
            # Update canary nodes
            await self._update_node_batch(fleet_update, canary_nodes)
            fleet_update.current_batch = 1
            
            # Wait and check canary success
            await asyncio.sleep(fleet_update.delay_between_batches)
            
            canary_success = await self._validate_canary_deployment(fleet_update, canary_nodes)
            
            if not canary_success:
                fleet_update.status = "canary_failed"
                logger.error(f"Canary deployment failed for fleet update {fleet_update.update_id}")
                return
                
            # Phase 2: Remaining nodes in batches
            remaining_nodes = fleet_update.node_ids[canary_count:]
            await self._execute_staged_rollout_for_nodes(fleet_update, remaining_nodes)
            
        except Exception as e:
            logger.error(f"Error in canary rollout: {e}")
            fleet_update.status = "failed"
            
    async def _execute_staged_rollout(self, fleet_update: FleetUpdate):
        """Execute staged rollout strategy"""
        await self._execute_staged_rollout_for_nodes(fleet_update, fleet_update.node_ids)
        
    async def _execute_staged_rollout_for_nodes(self, fleet_update: FleetUpdate, nodes: List[str]):
        """Execute staged rollout for a list of nodes"""
        try:
            batches = [nodes[i:i + fleet_update.batch_size] 
                      for i in range(0, len(nodes), fleet_update.batch_size)]
                      
            for i, batch in enumerate(batches):
                if fleet_update.status != "running":
                    break
                    
                logger.info(f"Updating batch {i + 1}/{len(batches)} ({len(batch)} nodes)")
                
                await self._update_node_batch(fleet_update, batch)
                fleet_update.current_batch += 1
                
                # Check failure threshold
                if len(fleet_update.failed_nodes) > fleet_update.max_failures:
                    fleet_update.status = "failed"
                    logger.error(f"Fleet update failed - too many failures ({len(fleet_update.failed_nodes)})")
                    break
                    
                # Wait between batches (except for last batch)
                if i < len(batches) - 1:
                    await asyncio.sleep(fleet_update.delay_between_batches)
                    
            if fleet_update.status == "running":
                fleet_update.status = "completed"
                
        except Exception as e:
            logger.error(f"Error in staged rollout: {e}")
            fleet_update.status = "failed"
            
    async def _execute_immediate_rollout(self, fleet_update: FleetUpdate):
        """Execute immediate rollout strategy"""
        try:
            await self._update_node_batch(fleet_update, fleet_update.node_ids)
            fleet_update.current_batch = 1
            fleet_update.status = "completed"
            
        except Exception as e:
            logger.error(f"Error in immediate rollout: {e}")
            fleet_update.status = "failed"
            
    async def _update_node_batch(self, fleet_update: FleetUpdate, nodes: List[str]):
        """Update a batch of nodes"""
        tasks = []
        
        for node_id in nodes:
            if node_id in fleet_update.pending_nodes:
                task = self._update_single_node(fleet_update, node_id)
                tasks.append(task)
                
        # Execute updates concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            node_id = nodes[i]
            if isinstance(result, Exception):
                logger.error(f"Error updating node {node_id}: {result}")
                if node_id in fleet_update.pending_nodes:
                    fleet_update.pending_nodes.remove(node_id)
                    fleet_update.failed_nodes.append(node_id)
            else:
                if node_id in fleet_update.pending_nodes:
                    fleet_update.pending_nodes.remove(node_id)
                    fleet_update.completed_nodes.append(node_id)
                    
    async def _update_single_node(self, fleet_update: FleetUpdate, node_id: str):
        """Update a single node"""
        try:
            await self.install_updates(
                node_id=node_id,
                snap_names=fleet_update.snap_names,
                force=False
            )
            
        except Exception as e:
            logger.error(f"Error updating node {node_id}: {e}")
            raise
            
    async def _validate_canary_deployment(self, fleet_update: FleetUpdate, canary_nodes: List[str]) -> bool:
        """Validate canary deployment success"""
        try:
            # Check how many canary nodes completed successfully
            successful_canaries = 0
            
            for node_id in canary_nodes:
                if node_id in fleet_update.completed_nodes:
                    successful_canaries += 1
                    
            # Require at least 80% success rate for canary
            success_rate = successful_canaries / len(canary_nodes)
            
            logger.info(f"Canary success rate: {success_rate:.2%} ({successful_canaries}/{len(canary_nodes)})")
            
            return success_rate >= 0.8
            
        except Exception as e:
            logger.error(f"Error validating canary deployment: {e}")
            return False
            
    async def _check_fleet_update_progress(self, node_id: str, status_data: Dict[str, Any]):
        """Check if status update affects fleet update progress"""
        # This would check if the node status affects any running fleet updates
        # and update the fleet update tracking accordingly
        pass
        
    async def _send_emergency_stop(self, node_id: str):
        """Send emergency stop command to a node"""
        try:
            node_url = await self._get_node_url(node_id)
            
            if not self.session:
                return
                
            async with self.session.post(
                f"{node_url}/api/v1/updates/emergency-stop",
                timeout=10
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Emergency stop failed for node {node_id}: HTTP {resp.status}")
                    
        except Exception as e:
            logger.warning(f"Error sending emergency stop to {node_id}: {e}")
            
    def _estimate_completion_time(self, fleet_update: FleetUpdate) -> Optional[datetime]:
        """Estimate completion time for fleet update"""
        if fleet_update.status != "running":
            return None
            
        # Simple estimation based on current progress and batch timing
        completed = len(fleet_update.completed_nodes) + len(fleet_update.failed_nodes)
        remaining = len(fleet_update.pending_nodes)
        
        if completed == 0:
            return None
            
        # Estimate time per node based on current progress
        elapsed = datetime.utcnow() - fleet_update.created_at
        time_per_node = elapsed.total_seconds() / completed
        
        # Estimate remaining time
        remaining_time = time_per_node * remaining
        
        return datetime.utcnow() + timedelta(seconds=remaining_time)
        
    async def _fleet_update_monitor(self):
        """Background task to monitor fleet updates"""
        while self.running:
            try:
                # Clean up completed fleet updates older than 24 hours
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                to_remove = []
                for update_id, fleet_update in self.fleet_updates.items():
                    if (fleet_update.status in ["completed", "failed", "cancelled"] and 
                        fleet_update.created_at < cutoff_time):
                        to_remove.append(update_id)
                        
                for update_id in to_remove:
                    del self.fleet_updates[update_id]
                    
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in fleet update monitor: {e}")
                await asyncio.sleep(60)
                
    async def _node_status_sync(self):
        """Background task to sync node statuses"""
        while self.running:
            try:
                # Periodically sync node statuses
                await asyncio.sleep(600)  # Every 10 minutes
                
            except Exception as e:
                logger.error(f"Error in node status sync: {e}")
                await asyncio.sleep(60)


# Global service instance
update_manager_service = UpdateManagerService()