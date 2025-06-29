#!/usr/bin/env python3
"""
Snapd REST API Manager for Ubuntu Core Network Management Client
Provides interface to snapd for remote management operations
"""

import asyncio
import aiohttp
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from urllib.parse import quote
import socket

logger = logging.getLogger(__name__)

class SnapdManager:
    """Manager for snapd REST API operations"""
    
    def __init__(self, socket_path: str = "/run/snapd.socket"):
        self.socket_path = socket_path
        self.session = None
        self.base_url = f"http+unix://{quote(socket_path, safe='')}"
        
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.UnixConnector(path=self.socket_path)
        self.session = aiohttp.ClientSession(connector=connector)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to snapd API"""
        if not self.session:
            raise RuntimeError("SnapdManager must be used as async context manager")
        
        url = f"http://localhost/v2{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"Snapd API Error {response.status}: {error_text}")
                
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            raise Exception(f"Connection error: {str(e)}")
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return await self._make_request('GET', '/system-info')
    
    async def list_snaps(self) -> Dict[str, Any]:
        """List all installed snaps"""
        return await self._make_request('GET', '/snaps')
    
    async def get_snap_info(self, snap_name: str) -> Dict[str, Any]:
        """Get information about a specific snap"""
        return await self._make_request('GET', f'/snaps/{snap_name}')
    
    async def install_snap(self, snap_name: str, channel: str = 'stable', 
                          dangerous: bool = False) -> Dict[str, Any]:
        """Install a snap"""
        data = {
            'action': 'install',
            'channel': channel
        }
        if dangerous:
            data['dangerous'] = True
        
        return await self._make_request('POST', f'/snaps/{snap_name}', json=data)
    
    async def remove_snap(self, snap_name: str, purge: bool = False) -> Dict[str, Any]:
        """Remove a snap"""
        data = {'action': 'remove'}
        if purge:
            data['purge'] = True
        
        return await self._make_request('POST', f'/snaps/{snap_name}', json=data)
    
    async def refresh_snap(self, snap_name: str, channel: Optional[str] = None) -> Dict[str, Any]:
        """Refresh (update) a snap"""
        data = {'action': 'refresh'}
        if channel:
            data['channel'] = channel
        
        return await self._make_request('POST', f'/snaps/{snap_name}', json=data)
    
    async def enable_snap(self, snap_name: str) -> Dict[str, Any]:
        """Enable a snap"""
        data = {'action': 'enable'}
        return await self._make_request('POST', f'/snaps/{snap_name}', json=data)
    
    async def disable_snap(self, snap_name: str) -> Dict[str, Any]:
        """Disable a snap"""
        data = {'action': 'disable'}
        return await self._make_request('POST', f'/snaps/{snap_name}', json=data)
    
    async def get_change_status(self, change_id: str) -> Dict[str, Any]:
        """Get status of an async operation"""
        return await self._make_request('GET', f'/changes/{change_id}')
    
    async def wait_for_change(self, change_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for an async operation to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = await self.get_change_status(change_id)
                status = response['result']['status']
                
                if status == 'Done':
                    return response
                elif status == 'Error':
                    error_msg = response['result'].get('err', 'Unknown error')
                    raise Exception(f"Operation failed: {error_msg}")
                
                await asyncio.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                logger.error(f"Error checking change status: {e}")
                await asyncio.sleep(2)
        
        raise TimeoutError(f"Operation {change_id} did not complete within {timeout} seconds")
    
    async def list_apps(self) -> Dict[str, Any]:
        """List snap applications"""
        return await self._make_request('GET', '/apps')
    
    async def start_app(self, app_name: str) -> Dict[str, Any]:
        """Start a snap application"""
        data = {'action': 'start'}
        return await self._make_request('POST', f'/apps', json=data, params={'names': app_name})
    
    async def stop_app(self, app_name: str) -> Dict[str, Any]:
        """Stop a snap application"""
        data = {'action': 'stop'}
        return await self._make_request('POST', f'/apps', json=data, params={'names': app_name})
    
    async def restart_app(self, app_name: str) -> Dict[str, Any]:
        """Restart a snap application"""
        data = {'action': 'restart'}
        return await self._make_request('POST', f'/apps', json=data, params={'names': app_name})
    
    async def get_interfaces(self) -> Dict[str, Any]:
        """Get interface connections"""
        return await self._make_request('GET', '/interfaces')
    
    async def connect_interface(self, plug_snap: str, plug_name: str, 
                               slot_snap: str, slot_name: str) -> Dict[str, Any]:
        """Connect a snap interface"""
        data = {
            'action': 'connect',
            'plugs': [{'snap': plug_snap, 'plug': plug_name}],
            'slots': [{'snap': slot_snap, 'slot': slot_name}]
        }
        return await self._make_request('POST', '/interfaces', json=data)
    
    async def disconnect_interface(self, plug_snap: str, plug_name: str, 
                                  slot_snap: str, slot_name: str) -> Dict[str, Any]:
        """Disconnect a snap interface"""
        data = {
            'action': 'disconnect',
            'plugs': [{'snap': plug_snap, 'plug': plug_name}],
            'slots': [{'snap': slot_snap, 'slot': slot_name}]
        }
        return await self._make_request('POST', '/interfaces', json=data)
    
    async def create_snapshot(self, snap_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create system snapshot"""
        data = {'action': 'save'}
        if snap_names:
            data['snaps'] = snap_names
        
        return await self._make_request('POST', '/snapshots', json=data)
    
    async def list_snapshots(self) -> Dict[str, Any]:
        """List available snapshots"""
        return await self._make_request('GET', '/snapshots')
    
    async def restore_snapshot(self, snapshot_id: str, 
                              snap_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Restore from snapshot"""
        data = {
            'action': 'restore',
            'snapshot': snapshot_id
        }
        
        if snap_names:
            data['snaps'] = snap_names
        
        return await self._make_request('POST', '/snapshots', json=data)
    
    async def check_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Check snapshot integrity"""
        data = {
            'action': 'check',
            'snapshot': snapshot_id
        }
        return await self._make_request('POST', '/snapshots', json=data)
    
    async def forget_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Delete a snapshot"""
        data = {
            'action': 'forget',
            'snapshot': snapshot_id
        }
        return await self._make_request('POST', '/snapshots', json=data)
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check of the system and snaps"""
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_healthy': True,
            'components': {}
        }
        
        try:
            # Check snapd health
            system_info = await self.get_system_info()
            health_status['components']['snapd'] = {
                'healthy': True,
                'version': system_info['result'].get('version', 'unknown'),
                'series': system_info['result'].get('series', 'unknown'),
                'architecture': system_info['result'].get('architecture', 'unknown'),
                'kernel_version': system_info['result'].get('kernel-version', 'unknown')
            }
        except Exception as e:
            health_status['components']['snapd'] = {
                'healthy': False,
                'error': str(e)
            }
            health_status['overall_healthy'] = False
        
        try:
            # Check snap services
            snaps = await self.list_snaps()
            active_snaps = [snap for snap in snaps['result'] if snap.get('active', False)]
            health_status['components']['snaps'] = {
                'healthy': True,
                'total_count': len(snaps['result']),
                'active_count': len(active_snaps),
                'installed_size': sum(snap.get('installed-size', 0) for snap in snaps['result']),
                'services': []
            }
            
            # Check individual snap health
            for snap in active_snaps[:10]:  # Limit to first 10 snaps to avoid timeout
                snap_health = await self._check_snap_health(snap['name'])
                health_status['components']['snaps']['services'].append(snap_health)
                
        except Exception as e:
            health_status['components']['snaps'] = {
                'healthy': False,
                'error': str(e)
            }
            health_status['overall_healthy'] = False
        
        try:
            # Check interfaces
            interfaces = await self.get_interfaces()
            connected_plugs = sum(1 for conn in interfaces['result']['established'] 
                                if conn.get('plug'))
            health_status['components']['interfaces'] = {
                'healthy': True,
                'connected_count': connected_plugs,
                'total_plugs': len(interfaces['result']['plugs']),
                'total_slots': len(interfaces['result']['slots'])
            }
        except Exception as e:
            health_status['components']['interfaces'] = {
                'healthy': False,
                'error': str(e)
            }
        
        return health_status
    
    async def _check_snap_health(self, snap_name: str) -> Dict[str, Any]:
        """Check health of individual snap"""
        try:
            snap_info = await self.get_snap_info(snap_name)
            snap_data = snap_info['result']
            
            # Check if snap has services
            apps_status = []
            if 'apps' in snap_data:
                for app_name, app_info in snap_data['apps'].items():
                    if app_info.get('daemon'):
                        apps_status.append({
                            'name': app_name,
                            'active': app_info.get('active', False),
                            'enabled': app_info.get('enabled', False)
                        })
            
            return {
                'name': snap_name,
                'healthy': snap_data.get('active', False),
                'status': snap_data.get('status', 'unknown'),
                'version': snap_data.get('version', 'unknown'),
                'revision': snap_data.get('revision', 'unknown'),
                'install_date': snap_data.get('install-date', None),
                'channel': snap_data.get('channel', 'unknown'),
                'apps': apps_status
            }
        except Exception as e:
            return {
                'name': snap_name,
                'healthy': False,
                'error': str(e)
            }
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            system_info = await self.get_system_info()
            snaps = await self.list_snaps()
            
            system_data = system_info['result']
            snap_data = snaps['result']
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'system': {
                    'version': system_data.get('version'),
                    'series': system_data.get('series'),
                    'kernel_version': system_data.get('kernel-version'),
                    'architecture': system_data.get('architecture'),
                    'virtualization': system_data.get('virtualization'),
                    'refresh': system_data.get('refresh', {})
                },
                'snaps': {
                    'total': len(snap_data),
                    'active': len([s for s in snap_data if s.get('active', False)]),
                    'size_total': sum(s.get('installed-size', 0) for s in snap_data),
                    'size_download': sum(s.get('download-size', 0) for s in snap_data),
                    'channels': {}
                }
            }
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def manage_snap_config(self, snap_name: str, config_options: Dict[str, Any]) -> Dict[str, Any]:
        """Manage snap-specific configuration"""
        return await self._make_request('PUT', f'/snaps/{snap_name}/conf', json=config_options)
    
    async def get_snap_config(self, snap_name: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get snap configuration"""
        params = {}
        if keys:
            params['keys'] = ','.join(keys)
        
        return await self._make_request('GET', f'/snaps/{snap_name}/conf', params=params)
    
    async def troubleshoot_snap(self, snap_name: str) -> Dict[str, Any]:
        """Troubleshoot snap issues"""
        issues = []
        recommendations = []
        
        try:
            # Check snap status
            snap_info = await self.get_snap_info(snap_name)
            snap_data = snap_info['result']
            
            if not snap_data.get('active', False):
                issues.append('Snap is not active')
                recommendations.append('Try enabling the snap with: snap enable {snap_name}')
            
            # Check for tracking channel issues
            channel = snap_data.get('channel', '')
            if 'edge' in channel:
                issues.append('Snap is using edge channel which may be unstable')
                recommendations.append('Consider switching to stable channel')
            
            # Check snap services
            if 'apps' in snap_data:
                inactive_services = []
                for app_name, app_info in snap_data['apps'].items():
                    if app_info.get('daemon') and not app_info.get('active', False):
                        inactive_services.append(app_name)
                
                if inactive_services:
                    issues.append(f"Services not running: {', '.join(inactive_services)}")
                    recommendations.append('Try restarting services with: snap restart {snap_name}')
            
            # Check interface connections
            interfaces = await self.get_interfaces()
            snap_plugs = [p for p in interfaces['result']['plugs'] if p['snap'] == snap_name]
            unconnected_plugs = [p for p in snap_plugs if not p.get('connections')]
            
            if unconnected_plugs:
                issues.append(f"Unconnected interfaces: {len(unconnected_plugs)}")
                recommendations.append('Check interface connections with: snap connections {snap_name}')
            
        except Exception as e:
            issues.append(f"Failed to analyze snap: {str(e)}")
        
        return {
            'snap_name': snap_name,
            'issues': issues,
            'recommendations': recommendations,
            'healthy': len(issues) == 0,
            'severity': 'high' if any('not active' in issue for issue in issues) else 'medium' if issues else 'low'
        }

class SnapdService:
    """Service wrapper for SnapdManager with lifecycle management"""
    
    def __init__(self):
        self.manager = None
        self.running = False
        
    async def start(self):
        """Start the snapd service"""
        logger.info("Starting snapd service")
        self.running = True
        self.manager = SnapdManager()
        
        # Test connection
        try:
            async with self.manager as mgr:
                system_info = await mgr.get_system_info()
                logger.info(f"Connected to snapd version {system_info['result'].get('version')}")
        except Exception as e:
            logger.error(f"Failed to connect to snapd: {e}")
            raise
    
    async def stop(self):
        """Stop the snapd service"""
        logger.info("Stopping snapd service")
        self.running = False
        
    async def get_manager(self) -> SnapdManager:
        """Get snapd manager instance"""
        if not self.running:
            raise RuntimeError("SnapdService not started")
        return self.manager
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform health check using manager"""
        async with await self.get_manager() as mgr:
            return await mgr.health_check()
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics using manager"""
        async with await self.get_manager() as mgr:
            return await mgr.get_system_metrics()

# Global service instance
snapd_service = SnapdService()