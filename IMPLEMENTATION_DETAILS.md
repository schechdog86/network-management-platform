# Detailed Implementation Plan with Code Snippets

## 1. Network Management Module Implementation

### 1.1 SSH Connection Manager

```python
# network_manager/ssh_client.py
import asyncio
import paramiko
import socket
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import logging

@dataclass
class ServerInfo:
    hostname: str
    ip_address: str
    port: int = 22
    username: str = "root"
    key_path: Optional[str] = None
    password: Optional[str] = None
    status: str = "unknown"
    
class SSHConnectionPool:
    def __init__(self, max_connections: int = 50):
        self.max_connections = max_connections
        self.connections: Dict[str, paramiko.SSHClient] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_connections)
        
    async def get_connection(self, server: ServerInfo) -> paramiko.SSHClient:
        key = f"{server.ip_address}:{server.port}"
        
        if key not in self.connections:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                if server.key_path:
                    private_key = paramiko.RSAKey.from_private_key_file(server.key_path)
                    client.connect(
                        server.ip_address,
                        port=server.port,
                        username=server.username,
                        pkey=private_key,
                        timeout=10
                    )
                else:
                    client.connect(
                        server.ip_address,
                        port=server.port,
                        username=server.username,
                        password=server.password,
                        timeout=10
                    )
                self.connections[key] = client
                return client
            except Exception as e:
                logging.error(f"Failed to connect to {server.ip_address}: {e}")
                raise
        
        return self.connections[key]
    
    async def execute_command(self, server: ServerInfo, command: str) -> Tuple[str, str, int]:
        """Execute command and return (stdout, stderr, exit_code)"""
        client = await self.get_connection(server)
        
        def _execute():
            stdin, stdout, stderr = client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            return stdout.read().decode(), stderr.read().decode(), exit_code
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _execute)
    
    async def execute_commands_bulk(self, servers: List[ServerInfo], commands: List[str]) -> Dict[str, List[Tuple[str, str, int]]]:
        """Execute multiple commands on multiple servers concurrently"""
        tasks = []
        for server in servers:
            for command in commands:
                task = asyncio.create_task(self.execute_command(server, command))
                tasks.append((server.ip_address, command, task))
        
        results = {}
        for ip, command, task in tasks:
            try:
                stdout, stderr, exit_code = await task
                if ip not in results:
                    results[ip] = []
                results[ip].append((stdout, stderr, exit_code))
            except Exception as e:
                logging.error(f"Failed to execute {command} on {ip}: {e}")
        
        return results

# Example usage:
async def discover_network_devices():
    ssh_pool = SSHConnectionPool()
    
    # Discover devices using nmap-style scanning
    import nmap
    nm = nmap.PortScanner()
    nm.scan('192.168.1.0/24', '22')
    
    servers = []
    for host in nm.all_hosts():
        if nm[host].state() == 'up' and 22 in nm[host]['tcp']:
            servers.append(ServerInfo(
                hostname=host,
                ip_address=host,
                username="admin"  # Would be configurable
            ))
    
    # Get system info from all servers
    commands = [
        "uname -a",
        "df -h",
        "free -m",
        "uptime"
    ]
    
    results = await ssh_pool.execute_commands_bulk(servers, commands)
    return results
```

Let me continue with more components...

### 1.2 SNMP Monitoring Integration

```python
# network_manager/snmp_monitor.py
from pysnmp.hlapi import *
import asyncio
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class SNMPDevice:
    ip_address: str
    community: str = "public"
    version: int = 2
    port: int = 161

class SNMPMonitor:
    """SNMP monitoring for network devices"""
    
    # Common OIDs
    SYSTEM_OID = '1.3.6.1.2.1.1.1.0'  # System description
    UPTIME_OID = '1.3.6.1.2.1.1.3.0'  # System uptime
    INTERFACES_OID = '1.3.6.1.2.1.2.2.1.2'  # Interface names
    INTERFACE_STATUS_OID = '1.3.6.1.2.1.2.2.1.8'  # Interface status
    CPU_USAGE_OID = '1.3.6.1.4.1.2021.11.9.0'  # CPU usage (if supported)
    MEMORY_USAGE_OID = '1.3.6.1.4.1.2021.4.6.0'  # Memory usage
    
    def __init__(self):
        self.devices: List[SNMPDevice] = []
    
    async def get_snmp_value(self, device: SNMPDevice, oid: str) -> Any:
        """Get single SNMP value"""
        for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
            SnmpEngine(),
            CommunityData(device.community, mpModel=device.version-1),
            UdpTransportTarget((device.ip_address, device.port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False):
            
            if errorIndication:
                raise Exception(f"SNMP Error: {errorIndication}")
            elif errorStatus:
                raise Exception(f"SNMP Error: {errorStatus.prettyPrint()}")
            else:
                for varBind in varBinds:
                    return varBind[1]
    
    async def get_device_info(self, device: SNMPDevice) -> Dict[str, Any]:
        """Get comprehensive device information"""
        try:
            system_desc = await self.get_snmp_value(device, self.SYSTEM_OID)
            uptime = await self.get_snmp_value(device, self.UPTIME_OID)
            
            return {
                'ip_address': device.ip_address,
                'system_description': str(system_desc),
                'uptime': int(uptime),
                'status': 'online',
                'timestamp': asyncio.get_event_loop().time()
            }
        except Exception as e:
            return {
                'ip_address': device.ip_address,
                'error': str(e),
                'status': 'offline',
                'timestamp': asyncio.get_event_loop().time()
            }
```

## 2. Advanced Backup System Implementation

### 2.1 ZFS Integration with Python

```python
# backup_manager/zfs_manager.py
import subprocess
import asyncio
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

@dataclass
class ZFSDataset:
    name: str
    mountpoint: str
    used: int
    available: int
    referenced: int
    compression: str
    snapshots: List[str]

@dataclass
class ZFSSnapshot:
    name: str
    dataset: str
    creation: datetime
    used: int
    referenced: int

class ZFSManager:
    """ZFS filesystem management for snapshots and backups"""
    
    def __init__(self):
        self.pools: List[str] = []
        self.datasets: Dict[str, ZFSDataset] = {}
    
    async def run_zfs_command(self, command: List[str]) -> str:
        """Execute ZFS command asynchronously"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"ZFS command failed: {stderr.decode()}")
            
            return stdout.decode().strip()
        except Exception as e:
            logging.error(f"ZFS command error: {e}")
            raise
    
    async def list_pools(self) -> List[str]:
        """List all ZFS pools"""
        output = await self.run_zfs_command(['zpool', 'list', '-H', '-o', 'name'])
        self.pools = output.split('\n') if output else []
        return self.pools
    
    async def list_datasets(self, pool: Optional[str] = None) -> Dict[str, ZFSDataset]:
        """List all datasets in pool or all pools"""
        cmd = ['zfs', 'list', '-H', '-o', 'name,mountpoint,used,avail,refer,compression']
        if pool:
            cmd.append(pool)
        
        output = await self.run_zfs_command(cmd)
        datasets = {}
        
        for line in output.split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 6:
                name = parts[0]
                snapshots = await self.list_snapshots(name)
                
                datasets[name] = ZFSDataset(
                    name=name,
                    mountpoint=parts[1],
                    used=self.parse_size(parts[2]),
                    available=self.parse_size(parts[3]),
                    referenced=self.parse_size(parts[4]),
                    compression=parts[5],
                    snapshots=snapshots
                )
        
        self.datasets = datasets
        return datasets
    
    async def list_snapshots(self, dataset: str) -> List[str]:
        """List snapshots for a dataset"""
        try:
            output = await self.run_zfs_command(['zfs', 'list', '-H', '-t', 'snapshot', '-o', 'name', '-r', dataset])
            return output.split('\n') if output else []
        except:
            return []
    
    async def create_snapshot(self, dataset: str, snapshot_name: Optional[str] = None) -> str:
        """Create ZFS snapshot"""
        if not snapshot_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            snapshot_name = f"auto_{timestamp}"
        
        full_name = f"{dataset}@{snapshot_name}"
        await self.run_zfs_command(['zfs', 'snapshot', full_name])
        logging.info(f"Created snapshot: {full_name}")
        return full_name
    
    async def destroy_snapshot(self, snapshot: str):
        """Destroy ZFS snapshot"""
        await self.run_zfs_command(['zfs', 'destroy', snapshot])
        logging.info(f"Destroyed snapshot: {snapshot}")
    
    async def send_snapshot(self, snapshot: str, destination: str, incremental_base: Optional[str] = None) -> int:
        """Send snapshot to destination (local file or SSH destination)"""
        cmd = ['zfs', 'send']
        
        if incremental_base:
            cmd.extend(['-i', incremental_base])
        
        cmd.append(snapshot)
        
        if destination.startswith('ssh://'):
            # Parse SSH destination
            ssh_parts = destination.replace('ssh://', '').split('/')
            ssh_host = ssh_parts[0]
            remote_dataset = '/'.join(ssh_parts[1:])
            
            ssh_cmd = f"ssh {ssh_host} 'zfs receive {remote_dataset}'"
            full_cmd = f"{' '.join(cmd)} | {ssh_cmd}"
            
            process = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            # Local file destination
            with open(destination, 'wb') as f:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=f,
                    stderr=asyncio.subprocess.PIPE
                )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"ZFS send failed: {stderr.decode()}")
        
        return process.returncode
    
    async def receive_snapshot(self, source: str, dataset: str) -> int:
        """Receive snapshot from source"""
        if source.startswith('ssh://'):
            # SSH source
            ssh_parts = source.replace('ssh://', '').split('/')
            ssh_host = ssh_parts[0]
            remote_snapshot = '/'.join(ssh_parts[1:])
            
            cmd = f"ssh {ssh_host} 'zfs send {remote_snapshot}' | zfs receive {dataset}"
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            # Local file source
            cmd = f"zfs receive {dataset} < {source}"
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"ZFS receive failed: {stderr.decode()}")
        
        return process.returncode
    
    def parse_size(self, size_str: str) -> int:
        """Parse ZFS size string to bytes"""
        if size_str == '-':
            return 0
        
        units = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
        
        if size_str[-1] in units:
            return int(float(size_str[:-1]) * units[size_str[-1]])
        return int(size_str)
    
    async def create_periodic_snapshots(self, dataset: str, retention_policy: Dict[str, int]):
        """Create periodic snapshots with retention policy"""
        # retention_policy example: {'hourly': 24, 'daily': 7, 'weekly': 4, 'monthly': 12}
        
        for period, count in retention_policy.items():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            snapshot_name = f"{period}_{timestamp}"
            
            await self.create_snapshot(dataset, snapshot_name)
            
            # Clean up old snapshots
            await self.cleanup_old_snapshots(dataset, period, count)
    
    async def cleanup_old_snapshots(self, dataset: str, period: str, keep_count: int):
        """Remove old snapshots beyond retention count"""
        snapshots = await self.list_snapshots(dataset)
        period_snapshots = [s for s in snapshots if f"@{period}_" in s]
        period_snapshots.sort(reverse=True)  # Newest first
        
        # Remove excess snapshots
        for snapshot in period_snapshots[keep_count:]:
            await self.destroy_snapshot(snapshot)

# Example usage
async def zfs_backup_example():
    zfs = ZFSManager()
    
    # List all datasets
    datasets = await zfs.list_datasets()
    
    for name, dataset in datasets.items():
        print(f"Dataset: {name}, Used: {dataset.used}, Available: {dataset.available}")
        
        # Create snapshot
        snapshot = await zfs.create_snapshot(name)
        
        # Send to backup location
        backup_file = f"/backup/{name.replace('/', '_')}.zfs"
        await zfs.send_snapshot(snapshot, backup_file)
```

### 2.2 Restic Integration for Deduplication

```python
# backup_manager/restic_manager.py
import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

@dataclass
class ResticRepository:
    path: str
    password: str
    encryption: str = "AES256"
    compression: str = "auto"

@dataclass
class ResticSnapshot:
    id: str
    time: datetime
    tree: str
    paths: List[str]
    hostname: str
    username: str
    tags: List[str]
    size: int

class ResticManager:
    """Restic backup manager with deduplication"""
    
    def __init__(self, repository: ResticRepository):
        self.repository = repository
        self.env = os.environ.copy()
        self.env['RESTIC_REPOSITORY'] = repository.path
        self.env['RESTIC_PASSWORD'] = repository.password
    
    async def run_restic_command(self, command: List[str], input_data: Optional[str] = None) -> str:
        """Execute restic command asynchronously"""
        try:
            cmd = ['restic'] + command
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env
            )
            
            stdout, stderr = await process.communicate(
                input=input_data.encode() if input_data else None
            )
            
            if process.returncode != 0:
                raise Exception(f"Restic command failed: {stderr.decode()}")
            
            return stdout.decode().strip()
        except Exception as e:
            logging.error(f"Restic command error: {e}")
            raise
    
    async def init_repository(self) -> bool:
        """Initialize restic repository"""
        try:
            await self.run_restic_command(['init'])
            logging.info(f"Initialized restic repository: {self.repository.path}")
            return True
        except Exception as e:
            if "already initialized" in str(e):
                return True
            raise
    
    async def backup(self, paths: List[str], tags: Optional[List[str]] = None, 
                    exclude_patterns: Optional[List[str]] = None) -> str:
        """Create backup of specified paths"""
        cmd = ['backup'] + paths
        
        if tags:
            for tag in tags:
                cmd.extend(['--tag', tag])
        
        if exclude_patterns:
            for pattern in exclude_patterns:
                cmd.extend(['--exclude', pattern])
        
        cmd.extend(['--json'])
        
        output = await self.run_restic_command(cmd)
        
        # Parse JSON output to get snapshot ID
        lines = output.split('\n')
        for line in lines:
            if line.strip():
                try:
                    data = json.loads(line)
                    if data.get('message_type') == 'summary':
                        snapshot_id = data.get('snapshot_id')
                        logging.info(f"Created backup snapshot: {snapshot_id}")
                        return snapshot_id
                except json.JSONDecodeError:
                    continue
        
        raise Exception("Failed to parse backup output")
    
    async def list_snapshots(self, paths: Optional[List[str]] = None, 
                           tags: Optional[List[str]] = None) -> List[ResticSnapshot]:
        """List snapshots in repository"""
        cmd = ['snapshots', '--json']
        
        if paths:
            cmd.extend(['--path'] + paths)
        
        if tags:
            for tag in tags:
                cmd.extend(['--tag', tag])
        
        output = await self.run_restic_command(cmd)
        snapshots_data = json.loads(output)
        
        snapshots = []
        for snapshot_data in snapshots_data:
            snapshots.append(ResticSnapshot(
                id=snapshot_data['id'],
                time=datetime.fromisoformat(snapshot_data['time'].replace('Z', '+00:00')),
                tree=snapshot_data['tree'],
                paths=snapshot_data['paths'],
                hostname=snapshot_data['hostname'],
                username=snapshot_data['username'],
                tags=snapshot_data.get('tags', []),
                size=0  # Size would need separate stats call
            ))
        
        return snapshots
    
    async def restore(self, snapshot_id: str, target_dir: str, 
                     include_patterns: Optional[List[str]] = None) -> bool:
        """Restore files from snapshot"""
        cmd = ['restore', snapshot_id, '--target', target_dir]
        
        if include_patterns:
            for pattern in include_patterns:
                cmd.extend(['--include', pattern])
        
        await self.run_restic_command(cmd)
        logging.info(f"Restored snapshot {snapshot_id} to {target_dir}")
        return True
    
    async def forget_snapshots(self, keep_policy: Dict[str, int]) -> List[str]:
        """Remove old snapshots based on retention policy"""
        cmd = ['forget', '--json']
        
        # Convert policy to restic arguments
        if 'last' in keep_policy:
            cmd.extend(['--keep-last', str(keep_policy['last'])])
        if 'hourly' in keep_policy:
            cmd.extend(['--keep-hourly', str(keep_policy['hourly'])])
        if 'daily' in keep_policy:
            cmd.extend(['--keep-daily', str(keep_policy['daily'])])
        if 'weekly' in keep_policy:
            cmd.extend(['--keep-weekly', str(keep_policy['weekly'])])
        if 'monthly' in keep_policy:
            cmd.extend(['--keep-monthly', str(keep_policy['monthly'])])
        if 'yearly' in keep_policy:
            cmd.extend(['--keep-yearly', str(keep_policy['yearly'])])
        
        output = await self.run_restic_command(cmd)
        result = json.loads(output)
        
        removed_snapshots = []
        for item in result:
            if 'remove' in item:
                removed_snapshots.extend([s['id'] for s in item['remove']])
        
        return removed_snapshots
    
    async def prune_repository(self) -> Dict[str, Any]:
        """Remove unreferenced data from repository"""
        output = await self.run_restic_command(['prune', '--json'])
        
        lines = output.split('\n')
        for line in lines:
            if line.strip():
                try:
                    data = json.loads(line)
                    if data.get('message_type') == 'summary':
                        return data
                except json.JSONDecodeError:
                    continue
        
        return {}
    
    async def check_repository(self) -> bool:
        """Check repository integrity"""
        try:
            await self.run_restic_command(['check'])
            return True
        except Exception as e:
            logging.error(f"Repository check failed: {e}")
            return False
    
    async def get_repository_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
        output = await self.run_restic_command(['stats', '--json'])
        return json.loads(output)

# Combined ZFS + Restic backup strategy
class HybridBackupManager:
    """Combines ZFS snapshots with Restic for optimal backup strategy"""
    
    def __init__(self, zfs_manager: ZFSManager, restic_manager: ResticManager):
        self.zfs = zfs_manager
        self.restic = restic_manager
    
    async def create_hybrid_backup(self, dataset: str, backup_paths: List[str], 
                                  tags: Optional[List[str]] = None) -> Dict[str, str]:
        """Create hybrid backup using ZFS snapshots + Restic"""
        
        # 1. Create ZFS snapshot for instant local backup
        zfs_snapshot = await self.zfs.create_snapshot(dataset)
        
        # 2. Mount snapshot read-only for restic backup
        snapshot_mount = f"/tmp/snapshot_mount_{dataset.replace('/', '_')}"
        os.makedirs(snapshot_mount, exist_ok=True)
        
        try:
            # Mount ZFS snapshot
            await self.zfs.run_zfs_command([
                'mount', '-t', 'zfs', '-o', 'ro', zfs_snapshot, snapshot_mount
            ])
            
            # 3. Create restic backup from snapshot
            snapshot_paths = [os.path.join(snapshot_mount, path.lstrip('/')) for path in backup_paths]
            restic_snapshot = await self.restic.backup(
                snapshot_paths,
                tags=(tags or []) + ['zfs-hybrid', dataset]
            )
            
            return {
                'zfs_snapshot': zfs_snapshot,
                'restic_snapshot': restic_snapshot,
                'status': 'success'
            }
            
        finally:
            # Cleanup: unmount snapshot
            try:
                await asyncio.create_subprocess_exec('umount', snapshot_mount)
                os.rmdir(snapshot_mount)
            except:
                pass
    
    async def restore_hybrid_backup(self, zfs_snapshot: str, restic_snapshot: str, 
                                   target_dir: str) -> bool:
        """Restore from hybrid backup"""
        
        # Try ZFS restore first (fastest)
        try:
            # Create temporary dataset for restore
            restore_dataset = f"{zfs_snapshot.split('@')[0]}_restore"
            await self.zfs.run_zfs_command(['zfs', 'clone', zfs_snapshot, restore_dataset])
            
            # Mount and copy data
            mount_point = f"/tmp/zfs_restore_{int(asyncio.get_event_loop().time())}"
            os.makedirs(mount_point, exist_ok=True)
            
            await self.zfs.run_zfs_command(['mount', restore_dataset, mount_point])
            
            # Copy data to target
            await asyncio.create_subprocess_exec('cp', '-r', f"{mount_point}/.", target_dir)
            
            # Cleanup
            await self.zfs.run_zfs_command(['umount', restore_dataset])
            await self.zfs.run_zfs_command(['zfs', 'destroy', restore_dataset])
            os.rmdir(mount_point)
            
            return True
            
        except Exception as e:
            logging.warning(f"ZFS restore failed, falling back to restic: {e}")
            
            # Fallback to restic restore
            return await self.restic.restore(restic_snapshot, target_dir)

# Example usage
async def hybrid_backup_example():
    # Initialize managers
    zfs = ZFSManager()
    
    restic_repo = ResticRepository(
        path="/backup/restic-repo",
        password="secure-password"
    )
    restic = ResticManager(restic_repo)
    await restic.init_repository()
    
    hybrid = HybridBackupManager(zfs, restic)
    
    # Create hybrid backup
    result = await hybrid.create_hybrid_backup(
        dataset="tank/important",
        backup_paths=["/home", "/etc"],
        tags=["daily", "production"]
    )
    
    print(f"Backup created: {result}")
    
    # Schedule periodic cleanup
    await restic.forget_snapshots({
        'daily': 7,
        'weekly': 4,
        'monthly': 12
    })
    
    await restic.prune_repository()
```

## 3. React Dashboard Implementation

### 3.1 Real-time Dashboard with WebSocket

```typescript
// frontend/src/components/Dashboard.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Alert,
  CircularProgress,
  useTheme
} from '@mui/material';
import { Line, Doughnut, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  BarElement,
} from 'chart.js';
import { io, Socket } from 'socket.io-client';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

interface SystemMetrics {
  timestamp: number;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_in: number;
  network_out: number;
  active_connections: number;
}

interface ServerStatus {
  id: string;
  hostname: string;
  ip_address: string;
  status: 'online' | 'offline' | 'warning';
  last_seen: string;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
}

interface BackupJob {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'failed' | 'scheduled';
  progress: number;
  start_time: string;
  estimated_completion?: string;
}

const Dashboard: React.FC = () => {
  const theme = useTheme();
  const [socket, setSocket] = useState<Socket | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics[]>([]);
  const [servers, setServers] = useState<ServerStatus[]>([]);
  const [backupJobs, setBackupJobs] = useState<BackupJob[]>([]);
  const [alerts, setAlerts] = useState<Array<{id: string, type: 'error' | 'warning' | 'info', message: string}>>([]);
  const [loading, setLoading] = useState(true);

  // Initialize WebSocket connection
  useEffect(() => {
    const newSocket = io(process.env.REACT_APP_WS_URL || 'ws://localhost:8000', {
      auth: {
        token: localStorage.getItem('auth_token')
      }
    });

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket');
      setLoading(false);
    });

    newSocket.on('system_metrics', (data: SystemMetrics) => {
      setSystemMetrics(prev => {
        const updated = [...prev, data];
        // Keep last 50 data points
        return updated.slice(-50);
      });
    });

    newSocket.on('server_status', (data: ServerStatus[]) => {
      setServers(data);
    });

    newSocket.on('backup_jobs', (data: BackupJob[]) => {
      setBackupJobs(data);
    });

    newSocket.on('alert', (alert: {type: 'error' | 'warning' | 'info', message: string}) => {
      const newAlert = {
        id: Date.now().toString(),
        ...alert
      };
      setAlerts(prev => [...prev, newAlert]);
      
      // Auto-remove alerts after 5 seconds
      setTimeout(() => {
        setAlerts(prev => prev.filter(a => a.id !== newAlert.id));
      }, 5000);
    });

    newSocket.on('disconnect', () => {
      console.log('Disconnected from WebSocket');
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, []);

  const removeAlert = useCallback((id: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== id));
  }, []);

  // Chart configurations
  const cpuChartData = {
    labels: systemMetrics.map(m => new Date(m.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'CPU Usage %',
        data: systemMetrics.map(m => m.cpu_usage),
        borderColor: theme.palette.primary.main,
        backgroundColor: theme.palette.primary.light,
        tension: 0.1,
      },
    ],
  };

  const memoryChartData = {
    labels: systemMetrics.map(m => new Date(m.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'Memory Usage %',
        data: systemMetrics.map(m => m.memory_usage),
        borderColor: theme.palette.secondary.main,
        backgroundColor: theme.palette.secondary.light,
        tension: 0.1,
      },
    ],
  };

  const serverStatusData = {
    labels: ['Online', 'Offline', 'Warning'],
    datasets: [
      {
        data: [
          servers.filter(s => s.status === 'online').length,
          servers.filter(s => s.status === 'offline').length,
          servers.filter(s => s.status === 'warning').length,
        ],
        backgroundColor: [
          theme.palette.success.main,
          theme.palette.error.main,
          theme.palette.warning.main,
        ],
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
      },
    },
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      {/* Alerts */}
      <Box mb={2}>
        {alerts.map(alert => (
          <Alert
            key={alert.id}
            severity={alert.type}
            onClose={() => removeAlert(alert.id)}
            sx={{ mb: 1 }}
          >
            {alert.message}
          </Alert>
        ))}
      </Box>

      {/* Main Dashboard Grid */}
      <Grid container spacing={3}>
        {/* System Overview */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Performance
              </Typography>
              <Box height={300}>
                <Grid container spacing={2} height="100%">
                  <Grid item xs={6}>
                    <Box height="100%">
                      <Typography variant="subtitle2" align="center">CPU Usage</Typography>
                      <Line data={cpuChartData} options={chartOptions} />
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box height="100%">
                      <Typography variant="subtitle2" align="center">Memory Usage</Typography>
                      <Line data={memoryChartData} options={chartOptions} />
                    </Box>
                  </Grid>
                </Grid>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Server Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Server Status
              </Typography>
              <Box height={250} display="flex" justifyContent="center" alignItems="center">
                <Doughnut 
                  data={serverStatusData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: 'bottom',
                      },
                    },
                  }} 
                />
              </Box>
              <Typography variant="body2" align="center" mt={1}>
                Total Servers: {servers.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Active Backup Jobs */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Active Backup Jobs
              </Typography>
              <Box>
                {backupJobs.filter(job => job.status === 'running').map(job => (
                  <Box key={job.id} mb={2}>
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2">{job.name}</Typography>
                      <Typography variant="body2">{job.progress}%</Typography>
                    </Box>
                    <Box mt={1}>
                      <div
                        style={{
                          width: '100%',
                          height: '8px',
                          backgroundColor: theme.palette.grey[300],
                          borderRadius: '4px',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            width: `${job.progress}%`,
                            height: '100%',
                            backgroundColor: theme.palette.primary.main,
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    </Box>
                  </Box>
                ))}
                {backupJobs.filter(job => job.status === 'running').length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    No active backup jobs
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Servers */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Server Overview
              </Typography>
              <Box>
                {servers.slice(0, 5).map(server => (
                  <Box key={server.id} display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Box>
                      <Typography variant="body2" fontWeight="bold">
                        {server.hostname}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {server.ip_address}
                      </Typography>
                    </Box>
                    <Box textAlign="right">
                      <Typography 
                        variant="caption" 
                        color={server.status === 'online' ? 'success.main' : server.status === 'offline' ? 'error.main' : 'warning.main'}
                      >
                        {server.status.toUpperCase()}
                      </Typography>
                      <Typography variant="caption" display="block">
                        CPU: {server.cpu_usage}%
                      </Typography>
                    </Box>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Network Activity */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Network Activity
              </Typography>
              <Box height={200}>
                <Bar
                  data={{
                    labels: systemMetrics.slice(-10).map(m => new Date(m.timestamp).toLocaleTimeString()),
                    datasets: [
                      {
                        label: 'Network In (MB/s)',
                        data: systemMetrics.slice(-10).map(m => m.network_in / 1024 / 1024),
                        backgroundColor: theme.palette.info.main,
                      },
                      {
                        label: 'Network Out (MB/s)',
                        data: systemMetrics.slice(-10).map(m => m.network_out / 1024 / 1024),
                        backgroundColor: theme.palette.warning.main,
                      },
                    ],
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: 'top',
                      },
                    },
                    scales: {
                      y: {
                        beginAtZero: true,
                      },
                    },
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
```

### 3.2 WebSocket Server Implementation

```python
# backend/websocket_server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import HTTPBearer
import asyncio
import json
import logging
from typing import Dict, List, Set
import redis
from datetime import datetime

from core.auth import verify_token
from services.system_monitor import SystemMonitor
from services.server_manager import ServerManager
from services.backup_manager import BackupManager

security = HTTPBearer()

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        
        # Initialize service monitors
        self.system_monitor = SystemMonitor()
        self.server_manager = ServerManager()
        self.backup_manager = BackupManager()
        
        # Start background tasks
        self.monitoring_task = None
        
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        logging.info(f"WebSocket connected: {connection_id} for user {user_id}")
        
        # Send initial data
        await self.send_initial_data(websocket)
        
        # Start monitoring if this is the first connection
        if len(self.active_connections) == 1:
            await self.start_monitoring()
    
    async def disconnect(self, connection_id: str, user_id: str):
        """Handle WebSocket disconnect"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logging.info(f"WebSocket disconnected: {connection_id}")
        
        # Stop monitoring if no connections
        if not self.active_connections:
            await self.stop_monitoring()
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections of a user"""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                if connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id].send_text(json.dumps(message))
                    except:
                        # Connection is broken, remove it
                        await self.disconnect(connection_id, user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection_id, websocket in self.active_connections.copy().items():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                # Connection is broken, remove it
                del self.active_connections[connection_id]
    
    async def send_initial_data(self, websocket: WebSocket):
        """Send initial dashboard data to new connection"""
        try:
            # Get current system metrics
            metrics = await self.system_monitor.get_current_metrics()
            await websocket.send_text(json.dumps({
                'type': 'system_metrics',
                'data': metrics
            }))
            
            # Get server status
            servers = await self.server_manager.get_all_servers_status()
            await websocket.send_text(json.dumps({
                'type': 'server_status',
                'data': servers
            }))
            
            # Get backup jobs
            backup_jobs = await self.backup_manager.get_active_jobs()
            await websocket.send_text(json.dumps({
                'type': 'backup_jobs',
                'data': backup_jobs
            }))
            
        except Exception as e:
            logging.error(f"Error sending initial data: {e}")
    
    async def start_monitoring(self):
        """Start background monitoring tasks"""
        if not self.monitoring_task:
            self.monitoring_task = asyncio.create_task(self.monitoring_loop())
    
    async def stop_monitoring(self):
        """Stop background monitoring tasks"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
    
    async def monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while True:
                # Collect system metrics
                metrics = await self.system_monitor.get_current_metrics()
                await self.broadcast({
                    'type': 'system_metrics',
                    'data': metrics
                })
                
                # Check server status
                servers = await self.server_manager.get_all_servers_status()
                await self.broadcast({
                    'type': 'server_status',
                    'data': servers
                })
                
                # Check backup jobs
                backup_jobs = await self.backup_manager.get_active_jobs()
                await self.broadcast({
                    'type': 'backup_jobs',
                    'data': backup_jobs
                })
                
                # Check for alerts
                alerts = await self.check_for_alerts(metrics, servers)
                for alert in alerts:
                    await self.broadcast({
                        'type': 'alert',
                        'data': alert
                    })
                
                await asyncio.sleep(5)  # Update every 5 seconds
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Monitoring loop error: {e}")
    
    async def check_for_alerts(self, metrics: dict, servers: list) -> List[dict]:
        """Check for system alerts"""
        alerts = []
        
        # CPU usage alert
        if metrics.get('cpu_usage', 0) > 90:
            alerts.append({
                'type': 'warning',
                'message': f"High CPU usage: {metrics['cpu_usage']:.1f}%"
            })
        
        # Memory usage alert
        if metrics.get('memory_usage', 0) > 85:
            alerts.append({
                'type': 'warning',
                'message': f"High memory usage: {metrics['memory_usage']:.1f}%"
            })
        
        # Disk usage alert
        if metrics.get('disk_usage', 0) > 90:
            alerts.append({
                'type': 'error',
                'message': f"Critical disk usage: {metrics['disk_usage']:.1f}%"
            })
        
        # Server offline alerts
        offline_servers = [s for s in servers if s.get('status') == 'offline']
        if offline_servers:
            alerts.append({
                'type': 'error',
                'message': f"{len(offline_servers)} server(s) offline"
            })
        
        return alerts

# WebSocket manager instance
ws_manager = WebSocketManager()

# WebSocket endpoint
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """WebSocket endpoint with authentication"""
    connection_id = f"ws_{datetime.now().timestamp()}"
    user_id = None
    
    try:
        # Authenticate user
        if token:
            user_data = await verify_token(token)
            if user_data:
                user_id = user_data.get('sub')
            else:
                await websocket.close(code=4001, reason="Invalid token")
                return
        else:
            await websocket.close(code=4000, reason="Authentication required")
            return
        
        # Connect WebSocket
        await ws_manager.connect(websocket, connection_id, user_id)
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle client messages
                await handle_client_message(message, user_id)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logging.warning(f"Invalid JSON from client: {data}")
            except Exception as e:
                logging.error(f"WebSocket message error: {e}")
        
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        if user_id:
            await ws_manager.disconnect(connection_id, user_id)

async def handle_client_message(message: dict, user_id: str):
    """Handle messages from WebSocket clients"""
    message_type = message.get('type')
    
    if message_type == 'ping':
        # Respond to ping
        await ws_manager.send_to_user(user_id, {'type': 'pong'})
    
    elif message_type == 'request_server_details':
        server_id = message.get('server_id')
        if server_id:
            details = await ws_manager.server_manager.get_server_details(server_id)
            await ws_manager.send_to_user(user_id, {
                'type': 'server_details',
                'data': details
            })
    
    elif message_type == 'start_backup':
        backup_config = message.get('config')
        if backup_config:
            job_id = await ws_manager.backup_manager.start_backup(backup_config)
            await ws_manager.send_to_user(user_id, {
                'type': 'backup_started',
                'data': {'job_id': job_id}
            })
```

## 4. AI Integration with LangChain

### 4.1 AI Chat Interface Backend

```python
# ai_manager/chat_interface.py
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import initialize_agent, AgentType
from langchain.tools import BaseTool
from langchain.schema import HumanMessage, AIMessage
import asyncio
from typing import List, Dict, Any, Optional
import logging
import json

from services.server_manager import ServerManager
from services.backup_manager import BackupManager
from services.deployment_manager import DeploymentManager

class ServerManagementTool(BaseTool):
    """Tool for server management operations"""
    
    name = "server_management"
    description = """
    Manage servers in the network. Can perform operations like:
    - List servers: list_servers()
    - Get server status: get_server_status(hostname_or_ip)
    - Execute command: execute_command(hostname_or_ip, command)
    - Restart server: restart_server(hostname_or_ip)
    - Wake server: wake_server(mac_address)
    """
    
    def __init__(self, server_manager: ServerManager):
        super().__init__()
        self.server_manager = server_manager
    
    def _run(self, query: str) -> str:
        """Execute server management operation"""
        try:
            # Parse the query to determine action
            if "list_servers" in query.lower():
                servers = asyncio.run(self.server_manager.get_all_servers())
                return json.dumps([{
                    'hostname': s.hostname,
                    'ip_address': s.ip_address,
                    'status': s.status
                } for s in servers])
            
            elif "get_server_status" in query.lower():
                # Extract hostname/IP from query
                import re
                match = re.search(r'get_server_status\(([^)]+)\)', query)
                if match:
                    target = match.group(1).strip('"\'')
                    status = asyncio.run(self.server_manager.get_server_status(target))
                    return json.dumps(status)
            
            elif "execute_command" in query.lower():
                # Extract hostname and command
                import re
                match = re.search(r'execute_command\(([^,]+),\s*([^)]+)\)', query)
                if match:
                    hostname = match.group(1).strip('"\'')
                    command = match.group(2).strip('"\'')
                    result = asyncio.run(self.server_manager.execute_command(hostname, command))
                    return json.dumps(result)
            
            elif "restart_server" in query.lower():
                match = re.search(r'restart_server\(([^)]+)\)', query)
                if match:
                    hostname = match.group(1).strip('"\'')
                    result = asyncio.run(self.server_manager.restart_server(hostname))
                    return json.dumps({'success': result})
            
            return "Invalid server management query. Please use one of the supported operations."
            
        except Exception as e:
            return f"Error executing server management operation: {str(e)}"

class BackupManagementTool(BaseTool):
    """Tool for backup operations"""
    
    name = "backup_management"
    description = """
    Manage backup operations. Can perform:
    - List backups: list_backups()
    - Start backup: start_backup(server_id, backup_type, paths)
    - Check backup status: check_backup_status(job_id)
    - Restore backup: restore_backup(backup_id, target_path)
    """
    
    def __init__(self, backup_manager: BackupManager):
        super().__init__()
        self.backup_manager = backup_manager
    
    def _run(self, query: str) -> str:
        """Execute backup operation"""
        try:
            if "list_backups" in query.lower():
                backups = asyncio.run(self.backup_manager.list_backups())
                return json.dumps(backups)
            
            elif "start_backup" in query.lower():
                # Parse backup parameters
                import re
                match = re.search(r'start_backup\(([^,]+),\s*([^,]+),\s*([^)]+)\)', query)
                if match:
                    server_id = match.group(1).strip('"\'')
                    backup_type = match.group(2).strip('"\'')
                    paths = match.group(3).strip('"\'')
                    
                    job_id = asyncio.run(self.backup_manager.start_backup({
                        'server_id': server_id,
                        'type': backup_type,
                        'paths': paths.split(',')
                    }))
                    return json.dumps({'job_id': job_id})
            
            elif "check_backup_status" in query.lower():
                match = re.search(r'check_backup_status\(([^)]+)\)', query)
                if match:
                    job_id = match.group(1).strip('"\'')
                    status = asyncio.run(self.backup_manager.get_job_status(job_id))
                    return json.dumps(status)
            
            return "Invalid backup management query."
            
        except Exception as e:
            return f"Error executing backup operation: {str(e)}"

class NetworkAnalysisTool(BaseTool):
    """Tool for network analysis and troubleshooting"""
    
    name = "network_analysis"
    description = """
    Analyze network performance and troubleshoot issues:
    - Check connectivity: ping_host(hostname_or_ip)
    - Port scan: scan_ports(hostname_or_ip, ports)
    - Network topology: discover_network(subnet)
    - Bandwidth test: test_bandwidth(source_server, target_server)
    """
    
    def __init__(self, network_manager):
        super().__init__()
        self.network_manager = network_manager
    
    def _run(self, query: str) -> str:
        """Execute network analysis"""
        try:
            if "ping_host" in query.lower():
                import re
                match = re.search(r'ping_host\(([^)]+)\)', query)
                if match:
                    hostname = match.group(1).strip('"\'')
                    result = asyncio.run(self.network_manager.ping_host(hostname))
                    return json.dumps(result)
            
            elif "scan_ports" in query.lower():
                match = re.search(r'scan_ports\(([^,]+),\s*([^)]+)\)', query)
                if match:
                    hostname = match.group(1).strip('"\'')
                    ports = match.group(2).strip('"\'')
                    result = asyncio.run(self.network_manager.scan_ports(hostname, ports))
                    return json.dumps(result)
            
            elif "discover_network" in query.lower():
                match = re.search(r'discover_network\(([^)]+)\)', query)
                if match:
                    subnet = match.group(1).strip('"\'')
                    result = asyncio.run(self.network_manager.discover_network(subnet))
                    return json.dumps(result)
            
            return "Invalid network analysis query."
            
        except Exception as e:
            return f"Error executing network analysis: {str(e)}"

class AINetworkAssistant:
    """AI-powered network management assistant"""
    
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            temperature=0.1,
            openai_api_key=openai_api_key,
            model_name="gpt-4"
        )
        
        # Initialize tools
        self.server_manager = ServerManager()
        self.backup_manager = BackupManager()
        self.deployment_manager = DeploymentManager()
        
        self.tools = [
            ServerManagementTool(self.server_manager),
            BackupManagementTool(self.backup_manager),
            NetworkAnalysisTool(None)  # Would need network manager instance
        ]
        
        # Initialize agent with tools
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
            memory=ConversationBufferWindowMemory(
                memory_key="chat_history",
                return_messages=True,
                k=10
            ),
            verbose=True
        )
        
        # System prompt
        self.system_prompt = """
        You are an AI assistant for network and server management. You have access to tools that can:
        
        1. Manage servers (list, status, execute commands, restart, wake)
        2. Handle backups (create, monitor, restore)
        3. Analyze network issues (ping, port scan, discovery)
        
        You should:
        - Be helpful and provide clear, actionable responses
        - Use the appropriate tools to gather information before answering
        - Explain technical concepts in an accessible way
        - Suggest best practices for network management
        - Alert users to potential security issues
        - Provide step-by-step guidance for complex tasks
        
        When using tools, always explain what you're doing and why.
        """
    
    async def chat(self, message: str, user_context: Optional[Dict] = None) -> str:
        """Process chat message and return response"""
        try:
            # Add system context if available
            if user_context:
                context_info = f"\nUser context: {json.dumps(user_context)}"
                message = message + context_info
            
            # Get response from agent
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.agent.run, message
            )
            
            return response
            
        except Exception as e:
            logging.error(f"AI chat error: {e}")
            return f"I encountered an error while processing your request: {str(e)}"
    
    async def suggest_actions(self, system_state: Dict) -> List[str]:
        """Suggest proactive actions based on system state"""
        suggestions = []
        
        # Analyze system metrics
        if system_state.get('cpu_usage', 0) > 80:
            suggestions.append("High CPU usage detected. Consider investigating running processes or scaling resources.")
        
        if system_state.get('disk_usage', 0) > 90:
            suggestions.append("Critical disk space. Immediate cleanup or storage expansion recommended.")
        
        # Check server status
        offline_servers = [s for s in system_state.get('servers', []) if s.get('status') == 'offline']
        if offline_servers:
            suggestions.append(f"Warning: {len(offline_servers)} server(s) are offline. Check network connectivity and power status.")
        
        # Backup recommendations
        last_backup = system_state.get('last_backup_time')
        if last_backup:
            import datetime
            time_since_backup = datetime.datetime.now() - datetime.datetime.fromisoformat(last_backup)
            if time_since_backup.days > 1:
                suggestions.append("No recent backups detected. Consider running a backup to protect your data.")
        
        return suggestions
    
    async def generate_maintenance_plan(self, servers: List[Dict]) -> str:
        """Generate a maintenance plan for the network"""
        
        maintenance_prompt = f"""
        Based on the following server inventory, generate a comprehensive maintenance plan:
        
        Servers: {json.dumps(servers, indent=2)}
        
        Please provide:
        1. Recommended maintenance schedule
        2. Critical updates needed
        3. Backup strategy
        4. Security recommendations
        5. Performance optimization opportunities
        
        Format the response as a structured maintenance plan.
        """
        
        return await self.chat(maintenance_prompt)

# FastAPI endpoint for AI chat
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict] = None

class ChatResponse(BaseModel):
    response: str
    suggestions: Optional[List[str]] = None

# Initialize AI assistant
ai_assistant = AINetworkAssistant(openai_api_key="your-openai-api-key")

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    chat_message: ChatMessage,
    current_user = Depends(get_current_user)
):
    """AI chat endpoint"""
    try:
        response = await ai_assistant.chat(
            chat_message.message, 
            chat_message.context
        )
        
        # Get system state for suggestions
        system_state = {
            'cpu_usage': 75,  # Would get from monitoring
            'disk_usage': 65,
            'servers': [],    # Would get from server manager
            'last_backup_time': '2025-06-23T10:00:00'
        }
        
        suggestions = await ai_assistant.suggest_actions(system_state)
        
        return ChatResponse(
            response=response,
            suggestions=suggestions
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-maintenance-plan")
async def generate_maintenance_plan(
    current_user = Depends(get_current_user)
):
    """Generate maintenance plan endpoint"""
    try:
        # Get current server list
        servers = await ai_assistant.server_manager.get_all_servers()
        server_data = [
            {
                'hostname': s.hostname,
                'ip_address': s.ip_address,
                'status': s.status,
                'last_updated': s.last_updated.isoformat() if s.last_updated else None
            } for s in servers
        ]
        
        plan = await ai_assistant.generate_maintenance_plan(server_data)
        
        return {'maintenance_plan': plan}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 5. Qt Desktop Application Implementation

### 5.1 Main Application Window

```python
# qt_gui/main_window.py
import sys
import asyncio
import qasync
from typing import Dict, List, Optional, Any
import json
import logging

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QMenuBar, QStatusBar, QToolBar, QSplitter,
    QDockWidget, QLabel, QPushButton, QProgressBar, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QGroupBox, QGridLayout, QFrame, QScrollArea, QSystemTrayIcon,
    QMenu, QAction, QMessageBox, QDialog, QDialogButtonBox
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QThread, QSize, QSettings, QPropertyAnimation,
    QEasingCurve, QRect, QUrl
)
from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont, QAction, QDesktopServices
)
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis

import requests
import websocket
import threading

from .dashboard_widget import DashboardWidget
from .server_management_widget import ServerManagementWidget
from .backup_management_widget import BackupManagementWidget
from .deployment_widget import DeploymentWidget
from .settings_dialog import SettingsDialog
from .ai_chat_widget import AIChatWidget

class NetworkManagerMainWindow(QMainWindow):
    """Main application window"""
    
    # Signals
    data_updated = Signal(dict)
    alert_received = Signal(str, str)  # type, message
    connection_status_changed = Signal(bool)
    
    def __init__(self):
        super().__init__()
        
        # Application settings
        self.settings = QSettings("NetworkManager", "MainApp")
        
        # WebSocket connection
        self.ws = None
        self.ws_thread = None
        self.is_connected = False
        
        # API base URL
        self.api_base_url = self.settings.value("api_base_url", "http://localhost:8000")
        self.auth_token = self.settings.value("auth_token", "")
        
        # Initialize UI
        self.init_ui()
        self.init_system_tray()
        self.init_websocket()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30 seconds
        
        # Load window state
        self.restore_window_state()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Network Management System")
        self.setWindowIcon(QIcon("assets/icons/network.png"))
        self.resize(1400, 900)
        
        # Create central widget with tabs
        self.central_widget = QTabWidget()
        self.setCentralWidget(self.central_widget)
        
        # Dashboard tab
        self.dashboard_widget = DashboardWidget(self)
        self.central_widget.addTab(self.dashboard_widget, "Dashboard")
        
        # Server management tab
        self.server_widget = ServerManagementWidget(self)
        self.central_widget.addTab(self.server_widget, "Servers")
        
        # Backup management tab
        self.backup_widget = BackupManagementWidget(self)
        self.central_widget.addTab(self.backup_widget, "Backups")
        
        # Deployment tab
        self.deployment_widget = DeploymentWidget(self)
        self.central_widget.addTab(self.deployment_widget, "Deployments")
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create status bar
        self.create_status_bar()
        
        # Create dockable AI chat
        self.create_ai_chat_dock()
        
        # Apply dark theme
        self.apply_theme()
        
        # Connect signals
        self.connect_signals()
    
    def create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        connect_action = QAction("&Connect to Server", self)
        connect_action.setShortcut("Ctrl+C")
        connect_action.triggered.connect(self.connect_to_server)
        file_menu.addAction(connect_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_data)
        view_menu.addAction(refresh_action)
        
        fullscreen_action = QAction("&Full Screen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """Create application toolbar"""
        toolbar = self.addToolBar("Main")
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.setIcon(QIcon("assets/icons/connect.png"))
        self.connect_button.clicked.connect(self.connect_to_server)
        toolbar.addWidget(self.connect_button)
        
        toolbar.addSeparator()
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.setIcon(QIcon("assets/icons/refresh.png"))
        refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_button)
        
        # Settings button
        settings_button = QPushButton("Settings")
        settings_button.setIcon(QIcon("assets/icons/settings.png"))
        settings_button.clicked.connect(self.open_settings)
        toolbar.addWidget(settings_button)
    
    def create_status_bar(self):
        """Create application status bar"""
        self.status_bar = self.statusBar()
        
        # Connection status
        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.connection_label)
        
        # Progress bar for operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Server count
        self.server_count_label = QLabel("Servers: 0")
        self.status_bar.addPermanentWidget(self.server_count_label)
    
    def create_ai_chat_dock(self):
        """Create AI chat dockable widget"""
        self.ai_chat_dock = QDockWidget("AI Assistant", self)
        self.ai_chat_widget = AIChatWidget(self)
        self.ai_chat_dock.setWidget(self.ai_chat_widget)
        self.ai_chat_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chat_dock)
        
        # Initially hide the AI chat
        self.ai_chat_dock.setVisible(False)
    
    def init_system_tray(self):
        """Initialize system tray icon"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(QIcon("assets/icons/network.png"))
            
            # Create tray menu
            tray_menu = QMenu()
            
            show_action = QAction("Show", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(QApplication.quit)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)
            self.tray_icon.show()
    
    def init_websocket(self):
        """Initialize WebSocket connection"""
        if self.auth_token:
            self.connect_websocket()
    
    def connect_websocket(self):
        """Connect to WebSocket server"""
        if self.ws_thread and self.ws_thread.is_alive():
            return
        
        ws_url = self.api_base_url.replace("http", "ws") + f"/ws?token={self.auth_token}"
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.data_updated.emit(data)
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON received: {message}")
        
        def on_error(ws, error):
            logging.error(f"WebSocket error: {error}")
            self.connection_status_changed.emit(False)
        
        def on_close(ws, close_status_code, close_msg):
            logging.info("WebSocket connection closed")
            self.connection_status_changed.emit(False)
        
        def on_open(ws):
            logging.info("WebSocket connection opened")
            self.connection_status_changed.emit(True)
        
        def run_websocket():
            websocket.enableTrace(True)
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            self.ws.run_forever()
        
        self.ws_thread = threading.Thread(target=run_websocket)
        self.ws_thread.daemon = True
        self.ws_thread.start()
    
    def connect_signals(self):
        """Connect internal signals"""
        self.data_updated.connect(self.handle_data_update)
        self.connection_status_changed.connect(self.handle_connection_status)
        self.alert_received.connect(self.handle_alert)
    
    def handle_data_update(self, data: dict):
        """Handle WebSocket data updates"""
        data_type = data.get('type')
        payload = data.get('data')
        
        if data_type == 'system_metrics':
            self.dashboard_widget.update_metrics(payload)
        elif data_type == 'server_status':
            self.server_widget.update_servers(payload)
            self.server_count_label.setText(f"Servers: {len(payload)}")
        elif data_type == 'backup_jobs':
            self.backup_widget.update_jobs(payload)
        elif data_type == 'alert':
            self.alert_received.emit(payload.get('type', 'info'), payload.get('message', ''))
    
    def handle_connection_status(self, connected: bool):
        """Handle connection status changes"""
        self.is_connected = connected
        
        if connected:
            self.connection_label.setText("Connected")
            self.connection_label.setStyleSheet("color: green; font-weight: bold;")
            self.connect_button.setText("Disconnect")
        else:
            self.connection_label.setText("Disconnected")
            self.connection_label.setStyleSheet("color: red; font-weight: bold;")
            self.connect_button.setText("Connect")
    
    def handle_alert(self, alert_type: str, message: str):
        """Handle alert notifications"""
        # Show in system tray
        if hasattr(self, 'tray_icon'):
            icon = QSystemTrayIcon.Critical if alert_type == 'error' else QSystemTrayIcon.Warning
            self.tray_icon.showMessage("Network Manager", message, icon, 5000)
        
        # Log to status bar
        self.status_bar.showMessage(f"{alert_type.upper()}: {message}", 10000)
    
    def apply_theme(self):
        """Apply dark theme to the application"""
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        
        QTabWidget::pane {
            border: 1px solid #555555;
            background-color: #3b3b3b;
        }
        
        QTabBar::tab {
            background-color: #555555;
            color: #ffffff;
            padding: 8px 16px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #0078d4;
        }
        
        QPushButton {
            background-color: #0078d4;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton:pressed {
            background-color: #005a9e;
        }
        
        QLabel {
            color: #ffffff;
        }
        
        QTreeWidget, QTableWidget {
            background-color: #3b3b3b;
            color: #ffffff;
            border: 1px solid #555555;
        }
        
        QTreeWidget::item:selected, QTableWidget::item:selected {
            background-color: #0078d4;
        }
        
        QStatusBar {
            background-color: #555555;
            color: #ffffff;
        }
        """
        
        self.setStyleSheet(dark_stylesheet)
    
    def connect_to_server(self):
        """Connect or disconnect from server"""
        if self.is_connected:
            if self.ws:
                self.ws.close()
        else:
            if not self.auth_token:
                self.open_settings()
            else:
                self.connect_websocket()
    
    def refresh_data(self):
        """Refresh all data from server"""
        if not self.is_connected:
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Send refresh request via WebSocket
        if self.ws:
            refresh_message = json.dumps({'type': 'refresh_all'})
            self.ws.send(refresh_message)
        
        # Hide progress bar after 2 seconds
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
    
    def toggle_fullscreen(self, checked: bool):
        """Toggle fullscreen mode"""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # Update settings
            self.api_base_url = dialog.get_api_url()
            self.auth_token = dialog.get_auth_token()
            
            # Save settings
            self.settings.setValue("api_base_url", self.api_base_url)
            self.settings.setValue("auth_token", self.auth_token)
            
            # Reconnect WebSocket
            if self.ws:
                self.ws.close()
            self.connect_websocket()
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Network Manager",
            """
            <h3>Network Management System</h3>
            <p>Version 1.0.0</p>
            <p>A comprehensive network and server management tool with AI assistance.</p>
            <p>Features:</p>
            <ul>
                <li>Real-time server monitoring</li>
                <li>Automated backup management</li>
                <li>PXE-based OS deployment</li>
                <li>AI-powered assistance</li>
                <li>Network topology visualization</li>
            </ul>
            """
        )
    
    def tray_icon_activated(self, reason):
        """Handle system tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
    
    def restore_window_state(self):
        """Restore window geometry and state"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Save window state
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Hide to system tray instead of closing
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Set application properties
    app.setApplicationName("Network Manager")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("NetworkManager")
    
    # Create and show main window
    window = NetworkManagerMainWindow()
    window.show()
    
    # Use qasync for async support in Qt
    with qasync.QEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_forever()

if __name__ == "__main__":
    main()
```
