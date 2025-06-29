#!/usr/bin/env python3
"""
Snapd REST API Client for Remote Ubuntu Core Management
Supports both local UNIX socket and remote HTTP/HTTPS connections
"""

import json
import os
import sys
import time
import socket
import requests
import urllib3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import argparse
import base64
import subprocess

# For Unix socket connections
import requests_unixsocket
requests_unixsocket.monkeypatch()


@dataclass
class SnapInfo:
    """Information about a snap"""
    name: str
    version: str
    revision: str
    channel: str
    publisher: str
    installed: bool
    confinement: str
    devmode: bool
    
    
@dataclass
class SystemInfo:
    """System information"""
    series: str
    version: str
    kernel_version: str
    architecture: str
    on_classic: bool
    managed: bool
    

class SnapdClient:
    """Client for interacting with snapd REST API"""
    
    def __init__(self, host: Optional[str] = None, port: int = 80, 
                 use_https: bool = False, auth_token: Optional[str] = None):
        """
        Initialize snapd client
        
        Args:
            host: Remote host IP/hostname. If None, use local socket
            port: Remote port (default 80)
            use_https: Use HTTPS for remote connections
            auth_token: Authentication token for remote access
        """
        self.host = host
        self.port = port
        self.use_https = use_https
        self.auth_token = auth_token
        
        if host:
            # Remote connection
            protocol = "https" if use_https else "http"
            self.base_url = f"{protocol}://{host}:{port}"
        else:
            # Local Unix socket
            self.base_url = "http+unix://%2Frun%2Fsnapd.socket"
            
        self.session = requests.Session()
        if auth_token:
            self.session.headers['Authorization'] = f'Bearer {auth_token}'
            
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make a request to snapd API"""
        url = f"{self.base_url}/v2/{endpoint}"
        
        try:
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                response = self.session.post(url, json=data)
            elif method == 'PUT':
                response = self.session.put(url, json=data)
            elif method == 'DELETE':
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {}
            
    def _wait_for_change(self, change_id: str, timeout: int = 300) -> bool:
        """Wait for a change to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self._request('GET', f'changes/{change_id}')
            if not result.get('result'):
                return False
                
            status = result['result']['status']
            
            if status == 'Done':
                return True
            elif status in ['Error', 'Aborted']:
                error = result['result'].get('err', 'Unknown error')
                print(f"Change failed: {error}")
                return False
                
            time.sleep(2)
            
        print(f"Timeout waiting for change {change_id}")
        return False
        
    # System information
    def get_system_info(self) -> Optional[SystemInfo]:
        """Get system information"""
        result = self._request('GET', 'system-info')
        if result.get('status') == 'OK':
            data = result['result']
            return SystemInfo(
                series=data.get('series', ''),
                version=data.get('version', ''),
                kernel_version=data.get('kernel-version', ''),
                architecture=data.get('architecture', ''),
                on_classic=data.get('on-classic', False),
                managed=data.get('managed', False)
            )
        return None
        
    # Snap management
    def list_snaps(self) -> List[SnapInfo]:
        """List all installed snaps"""
        result = self._request('GET', 'snaps')
        snaps = []
        
        if result.get('status') == 'OK':
            for snap_data in result.get('result', []):
                snaps.append(SnapInfo(
                    name=snap_data['name'],
                    version=snap_data['version'],
                    revision=snap_data['revision'],
                    channel=snap_data.get('channel', ''),
                    publisher=snap_data.get('publisher', {}).get('display-name', ''),
                    installed=True,
                    confinement=snap_data.get('confinement', ''),
                    devmode=snap_data.get('devmode', False)
                ))
                
        return snaps
        
    def get_snap(self, name: str) -> Optional[SnapInfo]:
        """Get information about a specific snap"""
        result = self._request('GET', f'snaps/{name}')
        
        if result.get('status') == 'OK':
            snap_data = result['result']
            return SnapInfo(
                name=snap_data['name'],
                version=snap_data['version'],
                revision=snap_data['revision'],
                channel=snap_data.get('channel', ''),
                publisher=snap_data.get('publisher', {}).get('display-name', ''),
                installed=True,
                confinement=snap_data.get('confinement', ''),
                devmode=snap_data.get('devmode', False)
            )
        return None
        
    def install_snap(self, name: str, channel: str = 'stable', 
                    classic: bool = False, devmode: bool = False) -> bool:
        """Install a snap"""
        data = {
            'action': 'install',
            'channel': channel
        }
        
        if classic:
            data['classic'] = True
        if devmode:
            data['devmode'] = True
            
        result = self._request('POST', f'snaps/{name}', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            print(f"Installing {name} (change: {change_id})...")
            return self._wait_for_change(change_id)
            
        return False
        
    def remove_snap(self, name: str) -> bool:
        """Remove a snap"""
        data = {'action': 'remove'}
        result = self._request('POST', f'snaps/{name}', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            print(f"Removing {name} (change: {change_id})...")
            return self._wait_for_change(change_id)
            
        return False
        
    def refresh_snap(self, name: str, channel: Optional[str] = None) -> bool:
        """Refresh (update) a snap"""
        data = {'action': 'refresh'}
        if channel:
            data['channel'] = channel
            
        result = self._request('POST', f'snaps/{name}', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            print(f"Refreshing {name} (change: {change_id})...")
            return self._wait_for_change(change_id)
            
        return False
        
    def enable_snap(self, name: str) -> bool:
        """Enable a snap"""
        data = {'action': 'enable'}
        result = self._request('POST', f'snaps/{name}', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    def disable_snap(self, name: str) -> bool:
        """Disable a snap"""
        data = {'action': 'disable'}
        result = self._request('POST', f'snaps/{name}', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    # Service management
    def list_services(self, snap_name: Optional[str] = None) -> List[Dict]:
        """List services"""
        if snap_name:
            result = self._request('GET', f'snaps/{snap_name}/services')
        else:
            result = self._request('GET', 'services')
            
        if result.get('status') == 'OK':
            return result.get('result', [])
            
        return []
        
    def start_service(self, snap_name: str, services: List[str]) -> bool:
        """Start snap services"""
        data = {
            'action': 'start',
            'services': services
        }
        
        result = self._request('POST', f'snaps/{snap_name}/services', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    def stop_service(self, snap_name: str, services: List[str]) -> bool:
        """Stop snap services"""
        data = {
            'action': 'stop',
            'services': services
        }
        
        result = self._request('POST', f'snaps/{snap_name}/services', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    def restart_service(self, snap_name: str, services: List[str]) -> bool:
        """Restart snap services"""
        data = {
            'action': 'restart',
            'services': services
        }
        
        result = self._request('POST', f'snaps/{snap_name}/services', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    # Configuration management
    def get_config(self, snap_name: str, keys: Optional[List[str]] = None) -> Dict:
        """Get snap configuration"""
        endpoint = f'snaps/{snap_name}/conf'
        if keys:
            endpoint += f'?keys={",".join(keys)}'
            
        result = self._request('GET', endpoint)
        
        if result.get('status') == 'OK':
            return result.get('result', {})
            
        return {}
        
    def set_config(self, snap_name: str, config: Dict) -> bool:
        """Set snap configuration"""
        result = self._request('PUT', f'snaps/{snap_name}/conf', config)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    # Logs
    def get_logs(self, snap_name: str, service_name: Optional[str] = None, 
                 lines: int = 100) -> List[str]:
        """Get snap logs"""
        params = {'n': lines}
        
        if service_name:
            endpoint = f'logs?services={snap_name}.{service_name}'
        else:
            endpoint = f'logs?services={snap_name}'
            
        result = self._request('GET', endpoint)
        
        if result.get('status') == 'OK':
            return result.get('result', [])
            
        return []
        
    # Interfaces
    def list_interfaces(self) -> Dict:
        """List all interfaces"""
        result = self._request('GET', 'interfaces')
        
        if result.get('status') == 'OK':
            return result.get('result', {})
            
        return {}
        
    def connect_interface(self, plug_snap: str, plug: str, 
                         slot_snap: str, slot: str) -> bool:
        """Connect an interface"""
        data = {
            'action': 'connect',
            'plugs': [{'snap': plug_snap, 'plug': plug}],
            'slots': [{'snap': slot_snap, 'slot': slot}]
        }
        
        result = self._request('POST', 'interfaces', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    def disconnect_interface(self, plug_snap: str, plug: str, 
                            slot_snap: str, slot: str) -> bool:
        """Disconnect an interface"""
        data = {
            'action': 'disconnect',
            'plugs': [{'snap': plug_snap, 'plug': plug}],
            'slots': [{'snap': slot_snap, 'slot': slot}]
        }
        
        result = self._request('POST', 'interfaces', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            return self._wait_for_change(change_id)
            
        return False
        
    # Recovery systems
    def list_recovery_systems(self) -> List[Dict]:
        """List recovery systems"""
        result = self._request('GET', 'systems')
        
        if result.get('status') == 'OK':
            return result.get('result', {}).get('systems', [])
            
        return []
        
    def create_recovery_system(self, label: str, validation_sets: List[str]) -> bool:
        """Create a new recovery system"""
        data = {
            'action': 'create',
            'label': label,
            'validation-sets': validation_sets
        }
        
        result = self._request('POST', 'systems', data)
        
        if result.get('status') == 'Accepted':
            change_id = result.get('change')
            print(f"Creating recovery system {label} (change: {change_id})...")
            return self._wait_for_change(change_id)
            
        return False


class RemoteManager:
    """High-level remote management interface"""
    
    def __init__(self, hosts: List[str], auth_token: Optional[str] = None):
        """
        Initialize remote manager for multiple hosts
        
        Args:
            hosts: List of host IPs/hostnames
            auth_token: Authentication token
        """
        self.clients = {}
        for host in hosts:
            self.clients[host] = SnapdClient(host=host, auth_token=auth_token)
            
    def get_fleet_status(self) -> Dict[str, Dict]:
        """Get status of all managed devices"""
        status = {}
        
        for host, client in self.clients.items():
            try:
                info = client.get_system_info()
                snaps = client.list_snaps()
                
                status[host] = {
                    'online': True,
                    'system': info.__dict__ if info else {},
                    'snap_count': len(snaps),
                    'snaps': [s.name for s in snaps]
                }
            except Exception as e:
                status[host] = {
                    'online': False,
                    'error': str(e)
                }
                
        return status
        
    def update_all(self, snap_name: str, channel: str = 'stable') -> Dict[str, bool]:
        """Update a snap across all devices"""
        results = {}
        
        for host, client in self.clients.items():
            print(f"Updating {snap_name} on {host}...")
            results[host] = client.refresh_snap(snap_name, channel)
            
        return results
        
    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command across all devices"""
        results = {}
        
        for host, client in self.clients.items():
            # This would require SSH or a custom snap with command execution
            # For now, just placeholder
            results[host] = f"Command execution not implemented"
            
        return results


def main():
    parser = argparse.ArgumentParser(description='Snapd Remote Management Client')
    parser.add_argument('--host', help='Remote host (local socket if not specified)')
    parser.add_argument('--port', type=int, default=80, help='Remote port')
    parser.add_argument('--token', help='Authentication token')
    parser.add_argument('--command', required=True, 
                       choices=['info', 'list', 'install', 'remove', 'refresh', 
                               'services', 'logs', 'interfaces'])
    parser.add_argument('--snap', help='Snap name')
    parser.add_argument('--channel', default='stable', help='Channel for install/refresh')
    parser.add_argument('--service', help='Service name')
    parser.add_argument('--lines', type=int, default=100, help='Number of log lines')
    
    args = parser.parse_args()
    
    # Create client
    client = SnapdClient(host=args.host, port=args.port, auth_token=args.token)
    
    # Execute command
    if args.command == 'info':
        info = client.get_system_info()
        if info:
            print(f"System: Ubuntu Core {info.series}")
            print(f"Version: {info.version}")
            print(f"Kernel: {info.kernel_version}")
            print(f"Architecture: {info.architecture}")
            
    elif args.command == 'list':
        snaps = client.list_snaps()
        print(f"{'Name':<20} {'Version':<15} {'Rev':<8} {'Channel':<15} {'Publisher'}")
        print("-" * 80)
        for snap in snaps:
            print(f"{snap.name:<20} {snap.version:<15} {snap.revision:<8} "
                  f"{snap.channel:<15} {snap.publisher}")
                  
    elif args.command == 'install' and args.snap:
        success = client.install_snap(args.snap, args.channel)
        print(f"Install {'successful' if success else 'failed'}")
        
    elif args.command == 'remove' and args.snap:
        success = client.remove_snap(args.snap)
        print(f"Remove {'successful' if success else 'failed'}")
        
    elif args.command == 'refresh' and args.snap:
        success = client.refresh_snap(args.snap, args.channel)
        print(f"Refresh {'successful' if success else 'failed'}")
        
    elif args.command == 'services':
        services = client.list_services(args.snap)
        for service in services:
            print(f"{service.get('name')}: {service.get('status')}")
            
    elif args.command == 'logs' and args.snap:
        logs = client.get_logs(args.snap, args.service, args.lines)
        for line in logs:
            print(line)
            
    elif args.command == 'interfaces':
        interfaces = client.list_interfaces()
        print(json.dumps(interfaces, indent=2))
        
    else:
        parser.print_help()
        

if __name__ == '__main__':
    main()