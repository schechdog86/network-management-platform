#!/usr/bin/env python3
"""
Backup manager for AI worker nodes.
Handles backing up model cache, configurations, and logs.
"""

import os
import json
import shutil
import tarfile
import hashlib
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import aiofiles
import asyncio

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backups for AI worker snap data"""
    
    def __init__(self):
        # Snap environment variables
        self.snap_name = os.environ.get('SNAP_NAME', 'ai-worker')
        self.snap_common = Path(os.environ.get('SNAP_COMMON', f'/var/snap/{self.snap_name}/common'))
        self.snap_data = Path(os.environ.get('SNAP_DATA', f'/var/snap/{self.snap_name}/current'))
        self.snap_user_common = Path(os.environ.get('SNAP_USER_COMMON', f'~/snap/{self.snap_name}/common')).expanduser()
        
        # Backup locations
        self.backup_dir = self.snap_common / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup configuration
        self.backup_items = {
            'models': {
                'path': self.snap_common / 'model-cache',
                'description': 'AI model cache',
                'compress': True,
                'priority': 'high'
            },
            'configs': {
                'path': self.snap_data / 'config',
                'description': 'Configuration files',
                'compress': True,
                'priority': 'critical'
            },
            'logs': {
                'path': self.snap_common / 'logs',
                'description': 'Application logs',
                'compress': True,
                'priority': 'low',
                'retention_days': 7
            },
            'ray_data': {
                'path': self.snap_common / 'ray',
                'description': 'Ray cluster data',
                'compress': True,
                'priority': 'medium'
            }
        }
        
        # Retention policy (days)
        self.retention_policy = {
            'critical': 30,
            'high': 14,
            'medium': 7,
            'low': 3
        }
        
    async def create_backup(self, items: Optional[List[str]] = None, 
                          backup_type: str = 'manual') -> Dict[str, Any]:
        """Create a backup of specified items or all items"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{self.snap_name}_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Determine items to backup
        if items:
            backup_items = {k: v for k, v in self.backup_items.items() if k in items}
        else:
            backup_items = self.backup_items
            
        results = {
            'backup_name': backup_name,
            'timestamp': timestamp,
            'type': backup_type,
            'items': {},
            'total_size': 0,
            'errors': []
        }
        
        # Create metadata file
        metadata = {
            'timestamp': datetime.utcnow().isoformat(),
            'snap_name': self.snap_name,
            'backup_type': backup_type,
            'items': list(backup_items.keys()),
            'hostname': os.uname().nodename
        }
        
        metadata_path = backup_path / 'metadata.json'
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
            
        # Backup each item
        for item_name, item_config in backup_items.items():
            try:
                item_result = await self._backup_item(
                    item_name, 
                    item_config, 
                    backup_path
                )
                results['items'][item_name] = item_result
                results['total_size'] += item_result['size']
                
            except Exception as e:
                logger.error(f"Error backing up {item_name}: {e}")
                results['errors'].append({
                    'item': item_name,
                    'error': str(e)
                })
                
        # Create final archive
        archive_path = self.backup_dir / f"{backup_name}.tar.gz"
        try:
            await self._create_archive(backup_path, archive_path)
            
            # Clean up temporary directory
            shutil.rmtree(backup_path)
            
            # Get archive size
            results['archive_path'] = str(archive_path)
            results['archive_size'] = archive_path.stat().st_size
            
        except Exception as e:
            logger.error(f"Error creating archive: {e}")
            results['errors'].append({
                'item': 'archive',
                'error': str(e)
            })
            
        # Clean up old backups
        await self._cleanup_old_backups()
        
        return results
        
    async def _backup_item(self, name: str, config: Dict[str, Any], 
                          backup_path: Path) -> Dict[str, Any]:
        """Backup a single item"""
        source_path = Path(config['path'])
        
        if not source_path.exists():
            logger.warning(f"Source path {source_path} does not exist, skipping")
            return {
                'status': 'skipped',
                'reason': 'source not found',
                'size': 0
            }
            
        dest_path = backup_path / name
        
        # Calculate size before backup
        if source_path.is_dir():
            size = sum(f.stat().st_size for f in source_path.rglob('*') if f.is_file())
        else:
            size = source_path.stat().st_size
            
        # Copy files
        if source_path.is_dir():
            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            
        # Calculate checksum
        checksum = await self._calculate_checksum(dest_path)
        
        return {
            'status': 'completed',
            'size': size,
            'checksum': checksum,
            'files': len(list(dest_path.rglob('*'))) if dest_path.is_dir() else 1
        }
        
    async def _create_archive(self, source_dir: Path, archive_path: Path):
        """Create compressed archive"""
        loop = asyncio.get_event_loop()
        
        def create_tar():
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(source_dir, arcname=source_dir.name)
                
        await loop.run_in_executor(None, create_tar)
        
    async def _calculate_checksum(self, path: Path) -> str:
        """Calculate SHA256 checksum of file or directory"""
        sha256 = hashlib.sha256()
        
        if path.is_file():
            async with aiofiles.open(path, 'rb') as f:
                while chunk := await f.read(8192):
                    sha256.update(chunk)
        else:
            # For directories, checksum all files
            for file_path in sorted(path.rglob('*')):
                if file_path.is_file():
                    async with aiofiles.open(file_path, 'rb') as f:
                        while chunk := await f.read(8192):
                            sha256.update(chunk)
                            
        return sha256.hexdigest()
        
    async def _cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        now = datetime.utcnow()
        
        for backup_file in self.backup_dir.glob('*.tar.gz'):
            try:
                # Parse backup filename
                parts = backup_file.stem.split('_')
                if len(parts) < 3:
                    continue
                    
                backup_type = parts[1]
                timestamp_str = f"{parts[2]}_{parts[3]}"
                backup_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                
                # Determine retention based on priority
                max_retention = max(self.retention_policy.values())
                retention_days = self.retention_policy.get('medium', 7)
                
                if backup_type == 'manual':
                    retention_days = max_retention
                    
                # Check if backup is too old
                if (now - backup_time).days > retention_days:
                    logger.info(f"Removing old backup: {backup_file}")
                    backup_file.unlink()
                    
            except Exception as e:
                logger.error(f"Error processing backup file {backup_file}: {e}")
                
    async def restore_backup(self, backup_name: str, 
                           items: Optional[List[str]] = None) -> Dict[str, Any]:
        """Restore from a backup"""
        archive_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Backup {backup_name} not found")
            
        results = {
            'backup_name': backup_name,
            'restored_items': {},
            'errors': []
        }
        
        # Extract archive
        temp_dir = self.backup_dir / f"restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract archive
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(temp_dir)
                
            # Find extracted backup directory
            backup_dir = next(temp_dir.iterdir())
            
            # Read metadata
            metadata_path = backup_dir / 'metadata.json'
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                    results['metadata'] = metadata
                    
            # Determine items to restore
            available_items = [d.name for d in backup_dir.iterdir() 
                             if d.is_dir() and d.name != 'metadata.json']
            
            if items:
                restore_items = [i for i in items if i in available_items]
            else:
                restore_items = available_items
                
            # Restore each item
            for item_name in restore_items:
                if item_name not in self.backup_items:
                    logger.warning(f"Unknown item {item_name}, skipping")
                    continue
                    
                try:
                    source = backup_dir / item_name
                    dest = Path(self.backup_items[item_name]['path'])
                    
                    # Backup current state before restoring
                    if dest.exists():
                        backup_current = dest.parent / f"{dest.name}.pre-restore"
                        if backup_current.exists():
                            shutil.rmtree(backup_current)
                        shutil.move(str(dest), str(backup_current))
                        
                    # Restore from backup
                    if source.is_dir():
                        shutil.copytree(source, dest, dirs_exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, dest)
                        
                    results['restored_items'][item_name] = {
                        'status': 'completed',
                        'path': str(dest)
                    }
                    
                except Exception as e:
                    logger.error(f"Error restoring {item_name}: {e}")
                    results['errors'].append({
                        'item': item_name,
                        'error': str(e)
                    })
                    
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir)
            
        return results
        
    async def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups"""
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob('*.tar.gz'), reverse=True):
            try:
                # Parse backup filename
                parts = backup_file.stem.split('_')
                if len(parts) < 3:
                    continue
                    
                backup_info = {
                    'name': backup_file.stem,
                    'type': parts[1],
                    'timestamp': f"{parts[2]}_{parts[3]}",
                    'size': backup_file.stat().st_size,
                    'path': str(backup_file)
                }
                
                # Try to get metadata
                # This would require extracting, so skip for performance
                
                backups.append(backup_info)
                
            except Exception as e:
                logger.error(f"Error processing backup {backup_file}: {e}")
                
        return backups
        
    async def backup_to_remote(self, backup_name: str, 
                             remote_url: str, 
                             method: str = 'rsync') -> Dict[str, Any]:
        """Backup to remote location using rsync or rclone"""
        archive_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Backup {backup_name} not found")
            
        results = {
            'backup_name': backup_name,
            'remote_url': remote_url,
            'method': method,
            'status': 'started'
        }
        
        try:
            if method == 'rsync':
                # Use rsync for SSH-accessible remotes
                cmd = [
                    'rsync',
                    '-avz',
                    '--progress',
                    str(archive_path),
                    remote_url
                ]
            elif method == 'rclone':
                # Use rclone for cloud storage
                cmd = [
                    'rclone',
                    'copy',
                    str(archive_path),
                    remote_url,
                    '--progress'
                ]
            else:
                raise ValueError(f"Unsupported backup method: {method}")
                
            # Run backup command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                results['status'] = 'completed'
                results['output'] = stdout.decode()
            else:
                results['status'] = 'failed'
                results['error'] = stderr.decode()
                
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            
        return results


async def main():
    """Test backup functionality"""
    logging.basicConfig(level=logging.INFO)
    
    manager = BackupManager()
    
    # Create a test backup
    logger.info("Creating backup...")
    result = await manager.create_backup(backup_type='test')
    print(json.dumps(result, indent=2))
    
    # List backups
    logger.info("\nListing backups...")
    backups = await manager.list_backups()
    for backup in backups:
        print(f"- {backup['name']} ({backup['size']} bytes)")


if __name__ == "__main__":
    asyncio.run(main())