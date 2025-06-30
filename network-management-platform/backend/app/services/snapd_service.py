"""
Snapd REST API Service
Manages snap operations across Ubuntu Core devices via snapd REST API
"""

import asyncio
import logging
import json
import aiohttp
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
import socket
from pathlib import Path

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager
from app.models.device import Device
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


@dataclass
class SnapInfo:
    """Snap information from snapd API"""
    name: str
    version: str
    revision: str
    status: str
    channel: str
    installed_size: Optional[int] = None
    install_date: Optional[datetime] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    developer: Optional[str] = None
    contact: Optional[str] = None
    website: Optional[str] = None
    license: Optional[str] = None
    tracking_channel: Optional[str] = None
    refresh_date: Optional[datetime] = None
    cohort_key: Optional[str] = None


@dataclass
class SnapChange:
    """Snap change operation from snapd API"""
    id: str
    kind: str
    summary: str
    status: str
    tasks: List[Dict[str, Any]]
    ready: bool
    spawn_time: datetime
    ready_time: Optional[datetime] = None
    err: Optional[str] = None


class SnapdConnection:
    """Connection to snapd daemon via REST API"""
    
    def __init__(self, endpoint: str, auth_token: Optional[str] = None):
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.BaseConnector] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def connect(self):
        """Establish connection to snapd"""
        try:
            # Check if endpoint is a Unix socket path
            if self.endpoint.startswith('/') or self.endpoint.startswith('unix://'):
                socket_path = self.endpoint.replace('unix://', '')
                self._connector = aiohttp.UnixConnector(path=socket_path)
                base_url = "http://snapd"
            else:
                # HTTP endpoint for remote snapd
                self._connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
                base_url = self.endpoint
                
            # Create session with timeout and headers
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
                
            self.session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers=headers,
                base_url=base_url
            )
            
            # Test connection
            await self.get_system_info()
            logger.info(f"Connected to snapd at {self.endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to connect to snapd at {self.endpoint}: {e}")
            await self.close()
            raise
            
    async def close(self):
        """Close connection to snapd"""
        if self.session:
            await self.session.close()
            self.session = None
            
        if self._connector:
            await self._connector.close()
            self._connector = None
            
    async def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make request to snapd API"""
        if not self.session:
            raise RuntimeError("Not connected to snapd")
            
        try:
            async with self.session.request(method, f"/v2{path}", **kwargs) as resp:
                if resp.status == 401:
                    raise PermissionError("Unauthorized access to snapd API")
                elif resp.status == 404:
                    raise FileNotFoundError(f"Snapd endpoint not found: {path}")
                elif resp.status >= 400:
                    error_text = await resp.text()
                    raise RuntimeError(f"Snapd API error {resp.status}: {error_text}")
                    
                return await resp.json()
                
        except aiohttp.ClientError as e:
            logger.error(f"Snapd API request failed: {e}")
            raise RuntimeError(f"Connection to snapd failed: {e}")
            
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        response = await self.request('GET', '/system-info')
        return response.get('result', {})
        
    async def list_snaps(self) -> List[SnapInfo]:
        """List installed snaps"""
        response = await self.request('GET', '/snaps')
        snaps_data = response.get('result', [])
        
        snaps = []
        for snap_data in snaps_data:
            snap = SnapInfo(
                name=snap_data['name'],
                version=snap_data['version'],
                revision=snap_data['revision'],
                status=snap_data['status'],
                channel=snap_data.get('channel', 'unknown'),
                installed_size=snap_data.get('installed-size'),
                summary=snap_data.get('summary'),
                description=snap_data.get('description'),
                developer=snap_data.get('developer'),
                contact=snap_data.get('contact'),
                website=snap_data.get('website'),
                license=snap_data.get('license'),
                tracking_channel=snap_data.get('tracking-channel'),
                cohort_key=snap_data.get('cohort-key')
            )
            
            # Parse dates
            if snap_data.get('install-date'):
                snap.install_date = datetime.fromisoformat(
                    snap_data['install-date'].replace('Z', '+00:00')
                )
            if snap_data.get('refresh-date'):
                snap.refresh_date = datetime.fromisoformat(
                    snap_data['refresh-date'].replace('Z', '+00:00')
                )
                
            snaps.append(snap)
            
        return snaps
        
    async def get_snap_info(self, snap_name: str) -> SnapInfo:
        """Get information about a specific snap"""
        response = await self.request('GET', f'/snaps/{snap_name}')
        snap_data = response.get('result', {})
        
        if not snap_data:
            raise FileNotFoundError(f"Snap '{snap_name}' not found")
            
        snap = SnapInfo(
            name=snap_data['name'],
            version=snap_data['version'],
            revision=snap_data['revision'],
            status=snap_data['status'],
            channel=snap_data.get('channel', 'unknown'),
            installed_size=snap_data.get('installed-size'),
            summary=snap_data.get('summary'),
            description=snap_data.get('description'),
            developer=snap_data.get('developer'),
            contact=snap_data.get('contact'),
            website=snap_data.get('website'),
            license=snap_data.get('license'),
            tracking_channel=snap_data.get('tracking-channel'),
            cohort_key=snap_data.get('cohort-key')
        )
        
        # Parse dates
        if snap_data.get('install-date'):
            snap.install_date = datetime.fromisoformat(
                snap_data['install-date'].replace('Z', '+00:00')
            )
        if snap_data.get('refresh-date'):
            snap.refresh_date = datetime.fromisoformat(
                snap_data['refresh-date'].replace('Z', '+00:00')
            )
            
        return snap
        
    async def install_snap(self, snap_name: str, channel: Optional[str] = None,
                          classic: bool = False, dangerous: bool = False) -> str:
        """Install a snap and return change ID"""
        data = {
            'action': 'install'
        }
        
        if channel:
            data['channel'] = channel
        if classic:
            data['classic'] = True
        if dangerous:
            data['dangerous'] = True
            
        response = await self.request('POST', f'/snaps/{snap_name}', json=data)
        return response.get('change')
        
    async def refresh_snap(self, snap_name: str, channel: Optional[str] = None) -> str:
        """Refresh a snap and return change ID"""
        data = {
            'action': 'refresh'
        }
        
        if channel:
            data['channel'] = channel
            
        response = await self.request('POST', f'/snaps/{snap_name}', json=data)
        return response.get('change')
        
    async def remove_snap(self, snap_name: str, purge: bool = False) -> str:
        """Remove a snap and return change ID"""
        data = {
            'action': 'remove'
        }
        
        if purge:
            data['purge'] = True
            
        response = await self.request('POST', f'/snaps/{snap_name}', json=data)
        return response.get('change')
        
    async def revert_snap(self, snap_name: str) -> str:
        """Revert a snap to previous revision and return change ID"""
        data = {
            'action': 'revert'
        }
        
        response = await self.request('POST', f'/snaps/{snap_name}', json=data)
        return response.get('change')
        
    async def enable_snap(self, snap_name: str) -> str:
        """Enable a snap and return change ID"""
        data = {
            'action': 'enable'
        }
        
        response = await self.request('POST', f'/snaps/{snap_name}', json=data)
        return response.get('change')
        
    async def disable_snap(self, snap_name: str) -> str:
        """Disable a snap and return change ID"""
        data = {
            'action': 'disable'
        }
        
        response = await self.request('POST', f'/snaps/{snap_name}', json=data)
        return response.get('change')
        
    async def get_change(self, change_id: str) -> SnapChange:
        """Get information about a change"""
        response = await self.request('GET', f'/changes/{change_id}')
        change_data = response.get('result', {})
        
        if not change_data:
            raise FileNotFoundError(f"Change '{change_id}' not found")
            
        change = SnapChange(
            id=change_data['id'],
            kind=change_data['kind'],
            summary=change_data['summary'],
            status=change_data['status'],
            tasks=change_data.get('tasks', []),
            ready=change_data['ready'],
            spawn_time=datetime.fromisoformat(
                change_data['spawn-time'].replace('Z', '+00:00')
            ),
            err=change_data.get('err')
        )
        
        if change_data.get('ready-time'):
            change.ready_time = datetime.fromisoformat(
                change_data['ready-time'].replace('Z', '+00:00')
            )
            
        return change
        
    async def wait_for_change(self, change_id: str, timeout: int = 300) -> bool:
        """Wait for a change to complete"""
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                change = await self.get_change(change_id)
                
                if change.ready:
                    if change.status == 'Done':
                        return True
                    elif change.status in ['Error', 'Hold']:
                        logger.error(f"Change {change_id} failed: {change.err}")
                        return False
                        
                # Still in progress, wait and retry
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error waiting for change {change_id}: {e}")
                await asyncio.sleep(5)
                
        logger.error(f"Change {change_id} timed out after {timeout} seconds")
        return False
        
    async def list_changes(self, snap_name: Optional[str] = None) -> List[SnapChange]:
        """List changes, optionally filtered by snap name"""
        params = {}
        if snap_name:
            params['for'] = snap_name
            
        response = await self.request('GET', '/changes', params=params)
        changes_data = response.get('result', [])
        
        changes = []
        for change_data in changes_data:
            change = SnapChange(
                id=change_data['id'],
                kind=change_data['kind'],
                summary=change_data['summary'],
                status=change_data['status'],
                tasks=change_data.get('tasks', []),
                ready=change_data['ready'],
                spawn_time=datetime.fromisoformat(
                    change_data['spawn-time'].replace('Z', '+00:00')
                ),
                err=change_data.get('err')
            )
            
            if change_data.get('ready-time'):
                change.ready_time = datetime.fromisoformat(
                    change_data['ready-time'].replace('Z', '+00:00')
                )
                
            changes.append(change)
            
        return changes
        
    async def get_connections(self) -> Dict[str, Any]:
        """Get snap interface connections"""
        response = await self.request('GET', '/connections')
        return response.get('result', {})
        
    async def connect_interface(self, plug: str, slot: str) -> str:
        """Connect a snap interface and return change ID"""
        data = {
            'action': 'connect',
            'plugs': [plug],
            'slots': [slot]
        }
        
        response = await self.request('POST', '/interfaces', json=data)
        return response.get('change')
        
    async def disconnect_interface(self, plug: str, slot: str) -> str:
        """Disconnect a snap interface and return change ID"""
        data = {
            'action': 'disconnect',
            'plugs': [plug],
            'slots': [slot]
        }
        
        response = await self.request('POST', '/interfaces', json=data)
        return response.get('change')


class SnapdService:
    """Service for managing snapd connections and operations"""
    
    def __init__(self):
        self.connections: Dict[str, SnapdConnection] = {}
        self.device_endpoints: Dict[str, str] = {}
        self.session_pool: Dict[str, aiohttp.ClientSession] = {}
        self.running = False
        
    async def start(self):
        """Start the snapd service"""
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self._connection_health_monitor())
        asyncio.create_task(self._cache_cleanup_task())
        
        logger.info("Snapd Service started")
        
    async def stop(self):
        """Stop the snapd service"""
        self.running = False
        
        # Close all connections
        for connection in self.connections.values():
            await connection.close()
            
        self.connections.clear()
        
        # Close session pool
        for session in self.session_pool.values():
            await session.close()
            
        self.session_pool.clear()
        
        logger.info("Snapd Service stopped")
        
    async def register_device(self, device_id: str, endpoint: str, 
                             auth_token: Optional[str] = None, db: Optional[AsyncSession] = None):
        """Register a device for snapd management"""
        try:
            # Test connection
            async with SnapdConnection(endpoint, auth_token) as conn:
                system_info = await conn.get_system_info()
                
            # Store device endpoint
            self.device_endpoints[device_id] = endpoint
            
            # Cache device info
            cache_key = f"snapd_device:{device_id}"
            device_info = {
                'endpoint': endpoint,
                'system_info': system_info,
                'registered_at': datetime.utcnow().isoformat(),
                'auth_token': auth_token
            }
            await cache_manager.set(cache_key, json.dumps(device_info), ttl=3600)
            
            # Update device in database if session provided
            if db:
                await db.execute(
                    update(Device)
                    .where(Device.id == device_id)
                    .values(
                        snapd_enabled=True,
                        snapd_endpoint=endpoint,
                        snap_config={'auth_token': bool(auth_token)}
                    )
                )
                await db.commit()
                
            logger.info(f"Registered device {device_id} for snapd management")
            
            # Broadcast registration event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': 'snapd_registered',
                'system_info': system_info,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return system_info
            
        except Exception as e:
            logger.error(f"Failed to register device {device_id}: {e}")
            raise
            
    async def unregister_device(self, device_id: str, db: Optional[AsyncSession] = None):
        """Unregister a device from snapd management"""
        try:
            # Close existing connection
            if device_id in self.connections:
                await self.connections[device_id].close()
                del self.connections[device_id]
                
            # Remove from device endpoints
            if device_id in self.device_endpoints:
                del self.device_endpoints[device_id]
                
            # Clear cache
            cache_key = f"snapd_device:{device_id}"
            await cache_manager.delete(cache_key)
            
            # Update device in database if session provided
            if db:
                await db.execute(
                    update(Device)
                    .where(Device.id == device_id)
                    .values(
                        snapd_enabled=False,
                        snapd_endpoint=None,
                        snap_config=None
                    )
                )
                await db.commit()
                
            logger.info(f"Unregistered device {device_id} from snapd management")
            
            # Broadcast unregistration event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': 'snapd_unregistered',
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to unregister device {device_id}: {e}")
            raise
            
    async def get_connection(self, device_id: str) -> SnapdConnection:
        """Get or create snapd connection for device"""
        if device_id not in self.connections:
            # Get device endpoint
            if device_id not in self.device_endpoints:
                # Try to load from cache
                cache_key = f"snapd_device:{device_id}"
                cached_info = await cache_manager.get(cache_key)
                
                if cached_info:
                    device_info = json.loads(cached_info)
                    endpoint = device_info['endpoint']
                    auth_token = device_info.get('auth_token')
                else:
                    raise ValueError(f"Device {device_id} not registered for snapd management")
            else:
                endpoint = self.device_endpoints[device_id]
                auth_token = None  # Would need to get from cache or database
                
            # Create new connection
            connection = SnapdConnection(endpoint, auth_token)
            await connection.connect()
            self.connections[device_id] = connection
            
        return self.connections[device_id]
        
    async def list_device_snaps(self, device_id: str) -> List[SnapInfo]:
        """List snaps installed on a device"""
        try:
            connection = await self.get_connection(device_id)
            snaps = await connection.list_snaps()
            
            # Cache the result
            cache_key = f"snapd_snaps:{device_id}"
            snaps_data = [
                {
                    'name': snap.name,
                    'version': snap.version,
                    'revision': snap.revision,
                    'status': snap.status,
                    'channel': snap.channel,
                    'installed_size': snap.installed_size,
                    'summary': snap.summary
                }
                for snap in snaps
            ]
            await cache_manager.set(cache_key, json.dumps(snaps_data), ttl=300)
            
            return snaps
            
        except Exception as e:
            logger.error(f"Failed to list snaps for device {device_id}: {e}")
            raise
            
    async def get_device_snap_info(self, device_id: str, snap_name: str) -> SnapInfo:
        """Get information about a specific snap on a device"""
        try:
            connection = await self.get_connection(device_id)
            return await connection.get_snap_info(snap_name)
            
        except Exception as e:
            logger.error(f"Failed to get snap info for {snap_name} on device {device_id}: {e}")
            raise
            
    async def install_snap_on_device(self, device_id: str, snap_name: str,
                                    channel: Optional[str] = None, 
                                    classic: bool = False,
                                    dangerous: bool = False) -> str:
        """Install a snap on a device"""
        try:
            connection = await self.get_connection(device_id)
            change_id = await connection.install_snap(snap_name, channel, classic, dangerous)
            
            # Broadcast installation started event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': 'snap_install_started',
                'snap_name': snap_name,
                'change_id': change_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Start monitoring the change
            asyncio.create_task(self._monitor_change(device_id, change_id, 'install', snap_name))
            
            return change_id
            
        except Exception as e:
            logger.error(f"Failed to install snap {snap_name} on device {device_id}: {e}")
            raise
            
    async def refresh_snap_on_device(self, device_id: str, snap_name: str,
                                    channel: Optional[str] = None) -> str:
        """Refresh a snap on a device"""
        try:
            connection = await self.get_connection(device_id)
            change_id = await connection.refresh_snap(snap_name, channel)
            
            # Broadcast refresh started event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': 'snap_refresh_started',
                'snap_name': snap_name,
                'change_id': change_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Start monitoring the change
            asyncio.create_task(self._monitor_change(device_id, change_id, 'refresh', snap_name))
            
            return change_id
            
        except Exception as e:
            logger.error(f"Failed to refresh snap {snap_name} on device {device_id}: {e}")
            raise
            
    async def remove_snap_from_device(self, device_id: str, snap_name: str,
                                     purge: bool = False) -> str:
        """Remove a snap from a device"""
        try:
            connection = await self.get_connection(device_id)
            change_id = await connection.remove_snap(snap_name, purge)
            
            # Broadcast removal started event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': 'snap_remove_started',
                'snap_name': snap_name,
                'change_id': change_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Start monitoring the change
            asyncio.create_task(self._monitor_change(device_id, change_id, 'remove', snap_name))
            
            return change_id
            
        except Exception as e:
            logger.error(f"Failed to remove snap {snap_name} from device {device_id}: {e}")
            raise
            
    async def get_device_changes(self, device_id: str, snap_name: Optional[str] = None) -> List[SnapChange]:
        """Get changes for a device"""
        try:
            connection = await self.get_connection(device_id)
            return await connection.list_changes(snap_name)
            
        except Exception as e:
            logger.error(f"Failed to get changes for device {device_id}: {e}")
            raise
            
    async def get_device_change_status(self, device_id: str, change_id: str) -> SnapChange:
        """Get status of a specific change on a device"""
        try:
            connection = await self.get_connection(device_id)
            return await connection.get_change(change_id)
            
        except Exception as e:
            logger.error(f"Failed to get change {change_id} status for device {device_id}: {e}")
            raise
            
    async def _monitor_change(self, device_id: str, change_id: str, 
                             operation: str, snap_name: str):
        """Monitor a change and broadcast status updates"""
        try:
            connection = await self.get_connection(device_id)
            
            # Wait for change to complete with timeout
            success = await connection.wait_for_change(change_id, timeout=1800)  # 30 minutes
            
            # Get final change status
            change = await connection.get_change(change_id)
            
            # Broadcast completion event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': f'snap_{operation}_completed',
                'snap_name': snap_name,
                'change_id': change_id,
                'success': success,
                'status': change.status,
                'error': change.err,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Clear cached snap list to force refresh
            cache_key = f"snapd_snaps:{device_id}"
            await cache_manager.delete(cache_key)
            
        except Exception as e:
            logger.error(f"Error monitoring change {change_id} for device {device_id}: {e}")
            
            # Broadcast error event
            await websocket_manager.broadcast_device_update(device_id, {
                'type': f'snap_{operation}_error',
                'snap_name': snap_name,
                'change_id': change_id,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
            
    async def _connection_health_monitor(self):
        """Background task to monitor connection health"""
        while self.running:
            try:
                # Check health of active connections
                unhealthy_devices = []
                
                for device_id, connection in self.connections.items():
                    try:
                        if connection.session and not connection.session.closed:
                            # Simple health check
                            await connection.get_system_info()
                        else:
                            unhealthy_devices.append(device_id)
                            
                    except Exception as e:
                        logger.warning(f"Health check failed for device {device_id}: {e}")
                        unhealthy_devices.append(device_id)
                        
                # Clean up unhealthy connections
                for device_id in unhealthy_devices:
                    try:
                        await self.connections[device_id].close()
                        del self.connections[device_id]
                        logger.info(f"Cleaned up unhealthy connection for device {device_id}")
                    except Exception as e:
                        logger.error(f"Error cleaning up connection for device {device_id}: {e}")
                        
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in connection health monitor: {e}")
                await asyncio.sleep(60)
                
    async def _cache_cleanup_task(self):
        """Background task to clean up expired cache entries"""
        while self.running:
            try:
                # This would clean up expired snapd-related cache entries
                # For now, Redis handles TTL automatically
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in cache cleanup task: {e}")
                await asyncio.sleep(60)


# Global service instance
snapd_service = SnapdService()