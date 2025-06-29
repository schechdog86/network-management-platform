"""
Comprehensive backup service integrating ZFS snapshots and Restic
"""

import asyncio
import subprocess
import logging
import json
import os
import tempfile
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager
from app.core.database import get_db
from app.models.backup import BackupJob, BackupStatus
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ZFSManager:
    """ZFS snapshot and management operations"""
    
    def __init__(self):
        self.zfs_command = "zfs"
        
    async def create_snapshot(self, dataset: str, snapshot_name: str = None) -> Dict[str, Any]:
        """Create ZFS snapshot"""
        try:
            if not snapshot_name:
                snapshot_name = f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            snapshot_path = f"{dataset}@{snapshot_name}"
            
            # Execute ZFS snapshot command
            result = await self._run_command([
                self.zfs_command, "snapshot", snapshot_path
            ])
            
            if result["success"]:
                # Get snapshot information
                snapshot_info = await self.get_snapshot_info(snapshot_path)
                
                return {
                    "success": True,
                    "snapshot_path": snapshot_path,
                    "snapshot_name": snapshot_name,
                    "dataset": dataset,
                    "created_at": datetime.now().isoformat(),
                    "info": snapshot_info
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to create snapshot"),
                    "dataset": dataset
                }
                
        except Exception as e:
            logger.error(f"Failed to create ZFS snapshot for {dataset}: {e}")
            return {
                "success": False,
                "error": str(e),
                "dataset": dataset
            }
    
    async def list_snapshots(self, dataset: str = None) -> List[Dict[str, Any]]:
        """List ZFS snapshots"""
        try:
            cmd = [self.zfs_command, "list", "-t", "snapshot", "-H", "-o", 
                   "name,creation,used,refer"]
            
            if dataset:
                cmd.extend(["-r", dataset])
            
            result = await self._run_command(cmd)
            
            if not result["success"]:
                return []
            
            snapshots = []
            for line in result["output"].strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        name_parts = parts[0].split('@')
                        if len(name_parts) == 2:
                            snapshots.append({
                                "name": parts[0],
                                "dataset": name_parts[0],
                                "snapshot": name_parts[1],
                                "creation": parts[1],
                                "used": parts[2],
                                "referenced": parts[3]
                            })
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Failed to list ZFS snapshots: {e}")
            return []
    
    async def delete_snapshot(self, snapshot_path: str) -> Dict[str, Any]:
        """Delete ZFS snapshot"""
        try:
            result = await self._run_command([
                self.zfs_command, "destroy", snapshot_path
            ])
            
            return {
                "success": result["success"],
                "snapshot_path": snapshot_path,
                "error": result.get("error") if not result["success"] else None
            }
            
        except Exception as e:
            logger.error(f"Failed to delete ZFS snapshot {snapshot_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "snapshot_path": snapshot_path
            }
    
    async def get_snapshot_info(self, snapshot_path: str) -> Dict[str, Any]:
        """Get detailed snapshot information"""
        try:
            result = await self._run_command([
                self.zfs_command, "get", "-H", "-p", "all", snapshot_path
            ])
            
            if not result["success"]:
                return {}
            
            properties = {}
            for line in result["output"].strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        properties[parts[1]] = parts[2]
            
            return properties
            
        except Exception as e:
            logger.error(f"Failed to get snapshot info for {snapshot_path}: {e}")
            return {}
    
    async def send_snapshot(self, snapshot_path: str, destination: str, 
                          incremental_base: str = None) -> Dict[str, Any]:
        """Send ZFS snapshot to destination"""
        try:
            cmd = [self.zfs_command, "send"]
            
            if incremental_base:
                cmd.extend(["-i", incremental_base])
            
            cmd.append(snapshot_path)
            
            # If destination is a file
            if destination.startswith('/') or destination.startswith('./'):
                with open(destination, 'wb') as f:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=f,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    _, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        file_size = os.path.getsize(destination)
                        return {
                            "success": True,
                            "snapshot_path": snapshot_path,
                            "destination": destination,
                            "size_bytes": file_size
                        }
                    else:
                        return {
                            "success": False,
                            "error": stderr.decode() if stderr else "Send failed",
                            "snapshot_path": snapshot_path
                        }
            else:
                # Send to another ZFS dataset (not implemented in this example)
                return {
                    "success": False,
                    "error": "Remote ZFS send not implemented",
                    "snapshot_path": snapshot_path
                }
                
        except Exception as e:
            logger.error(f"Failed to send ZFS snapshot {snapshot_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "snapshot_path": snapshot_path
            }
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Execute ZFS command"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "success": process.returncode == 0,
                "output": stdout.decode() if stdout else "",
                "error": stderr.decode() if stderr else "",
                "return_code": process.returncode
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "return_code": -1
            }


class ResticManager:
    """Restic backup and repository management"""
    
    def __init__(self):
        self.restic_command = "restic"
        self.repositories: Dict[str, str] = {}
        
    def add_repository(self, name: str, path: str, password: str = None):
        """Add a Restic repository"""
        self.repositories[name] = {
            "path": path,
            "password": password or os.environ.get("RESTIC_PASSWORD", "")
        }
    
    async def init_repository(self, repo_name: str, repo_path: str, 
                            password: str) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        try:
            env = os.environ.copy()
            env["RESTIC_PASSWORD"] = password
            env["RESTIC_REPOSITORY"] = repo_path
            
            result = await self._run_restic_command(["init"], env=env)
            
            if result["success"]:
                self.add_repository(repo_name, repo_path, password)
                
                return {
                    "success": True,
                    "repository": repo_name,
                    "path": repo_path,
                    "message": "Repository initialized successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to initialize repository"),
                    "repository": repo_name
                }
                
        except Exception as e:
            logger.error(f"Failed to initialize Restic repository {repo_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "repository": repo_name
            }
    
    async def backup_paths(self, repo_name: str, paths: List[str], 
                          tags: List[str] = None, exclude: List[str] = None) -> Dict[str, Any]:
        """Backup specified paths to Restic repository"""
        try:
            if repo_name not in self.repositories:
                return {
                    "success": False,
                    "error": f"Repository {repo_name} not configured"
                }
            
            repo_config = self.repositories[repo_name]
            env = os.environ.copy()
            env["RESTIC_PASSWORD"] = repo_config["password"]
            env["RESTIC_REPOSITORY"] = repo_config["path"]
            
            cmd = ["backup"] + paths
            
            if tags:
                for tag in tags:
                    cmd.extend(["--tag", tag])
            
            if exclude:
                for exclude_pattern in exclude:
                    cmd.extend(["--exclude", exclude_pattern])
            
            # Add progress reporting
            cmd.extend(["--json"])
            
            result = await self._run_restic_command(cmd, env=env)
            
            if result["success"]:
                # Parse JSON output for backup statistics
                backup_stats = self._parse_backup_output(result["output"])
                
                return {
                    "success": True,
                    "repository": repo_name,
                    "paths": paths,
                    "stats": backup_stats,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Backup failed"),
                    "repository": repo_name,
                    "paths": paths
                }
                
        except Exception as e:
            logger.error(f"Failed to backup paths to {repo_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "repository": repo_name,
                "paths": paths
            }
    
    async def list_snapshots(self, repo_name: str) -> List[Dict[str, Any]]:
        """List snapshots in Restic repository"""
        try:
            if repo_name not in self.repositories:
                return []
            
            repo_config = self.repositories[repo_name]
            env = os.environ.copy()
            env["RESTIC_PASSWORD"] = repo_config["password"]
            env["RESTIC_REPOSITORY"] = repo_config["path"]
            
            result = await self._run_restic_command(["snapshots", "--json"], env=env)
            
            if result["success"]:
                snapshots_data = json.loads(result["output"])
                return snapshots_data
            else:
                logger.error(f"Failed to list snapshots: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to list Restic snapshots for {repo_name}: {e}")
            return []
    
    async def restore_snapshot(self, repo_name: str, snapshot_id: str, 
                             target_path: str, include: List[str] = None) -> Dict[str, Any]:
        """Restore snapshot from Restic repository"""
        try:
            if repo_name not in self.repositories:
                return {
                    "success": False,
                    "error": f"Repository {repo_name} not configured"
                }
            
            repo_config = self.repositories[repo_name]
            env = os.environ.copy()
            env["RESTIC_PASSWORD"] = repo_config["password"]
            env["RESTIC_REPOSITORY"] = repo_config["path"]
            
            cmd = ["restore", snapshot_id, "--target", target_path]
            
            if include:
                for include_pattern in include:
                    cmd.extend(["--include", include_pattern])
            
            result = await self._run_restic_command(cmd, env=env)
            
            return {
                "success": result["success"],
                "repository": repo_name,
                "snapshot_id": snapshot_id,
                "target_path": target_path,
                "error": result.get("error") if not result["success"] else None
            }
            
        except Exception as e:
            logger.error(f"Failed to restore snapshot {snapshot_id} from {repo_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "repository": repo_name,
                "snapshot_id": snapshot_id
            }
    
    async def check_repository(self, repo_name: str) -> Dict[str, Any]:
        """Check repository integrity"""
        try:
            if repo_name not in self.repositories:
                return {
                    "success": False,
                    "error": f"Repository {repo_name} not configured"
                }
            
            repo_config = self.repositories[repo_name]
            env = os.environ.copy()
            env["RESTIC_PASSWORD"] = repo_config["password"]
            env["RESTIC_REPOSITORY"] = repo_config["path"]
            
            result = await self._run_restic_command(["check", "--json"], env=env)
            
            return {
                "success": result["success"],
                "repository": repo_name,
                "output": result.get("output", ""),
                "error": result.get("error") if not result["success"] else None
            }
            
        except Exception as e:
            logger.error(f"Failed to check repository {repo_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "repository": repo_name
            }
    
    def _parse_backup_output(self, output: str) -> Dict[str, Any]:
        """Parse Restic backup JSON output"""
        try:
            lines = output.strip().split('\n')
            summary_line = lines[-1]  # Last line contains summary
            summary = json.loads(summary_line)
            
            return {
                "files_new": summary.get("files_new", 0),
                "files_changed": summary.get("files_changed", 0),
                "files_unmodified": summary.get("files_unmodified", 0),
                "dirs_new": summary.get("dirs_new", 0),
                "dirs_changed": summary.get("dirs_changed", 0),
                "dirs_unmodified": summary.get("dirs_unmodified", 0),
                "data_added": summary.get("data_added", 0),
                "total_files_processed": summary.get("total_files_processed", 0),
                "total_bytes_processed": summary.get("total_bytes_processed", 0),
                "total_duration": summary.get("total_duration", 0),
                "snapshot_id": summary.get("snapshot_id", "")
            }
            
        except Exception as e:
            logger.error(f"Failed to parse backup output: {e}")
            return {}
    
    async def _run_restic_command(self, cmd: List[str], env: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute Restic command"""
        try:
            full_cmd = [self.restic_command] + cmd
            
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env or os.environ
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "success": process.returncode == 0,
                "output": stdout.decode() if stdout else "",
                "error": stderr.decode() if stderr else "",
                "return_code": process.returncode
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "return_code": -1
            }


class HybridBackupService:
    """Hybrid backup service combining ZFS and Restic"""
    
    def __init__(self):
        self.zfs_manager = ZFSManager()
        self.restic_manager = ResticManager()
        self.backup_jobs: Dict[str, asyncio.Task] = {}
        
    async def create_hybrid_backup(self, backup_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create hybrid backup using ZFS snapshots and Restic"""
        try:
            job_id = f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Validate configuration
            required_fields = ["name", "datasets", "repository", "retention"]
            for field in required_fields:
                if field not in backup_config:
                    return {
                        "success": False,
                        "error": f"Missing required field: {field}",
                        "job_id": job_id
                    }
            
            # Start backup job
            backup_task = asyncio.create_task(
                self._execute_hybrid_backup(job_id, backup_config)
            )
            
            self.backup_jobs[job_id] = backup_task
            
            # Store job info in cache
            await cache_manager.set(f"backup_job:{job_id}", {
                "id": job_id,
                "name": backup_config["name"],
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "config": backup_config
            }, ttl=3600)
            
            return {
                "success": True,
                "job_id": job_id,
                "name": backup_config["name"],
                "status": "started",
                "message": "Hybrid backup job started"
            }
            
        except Exception as e:
            logger.error(f"Failed to create hybrid backup: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_hybrid_backup(self, job_id: str, config: Dict[str, Any]):
        """Execute the hybrid backup process"""
        try:
            # Update job status
            await self._update_job_status(job_id, "creating_snapshots")
            
            # Phase 1: Create ZFS snapshots
            snapshots_created = []
            for dataset in config["datasets"]:
                snapshot_result = await self.zfs_manager.create_snapshot(dataset)
                if snapshot_result["success"]:
                    snapshots_created.append(snapshot_result)
                    
                    # Broadcast progress
                    await websocket_manager.connection_manager.broadcast_to_channel(
                        "backups",
                        {
                            "type": "backup_progress",
                            "job_id": job_id,
                            "phase": "snapshot_created",
                            "dataset": dataset,
                            "snapshot": snapshot_result["snapshot_path"]
                        }
                    )
                else:
                    logger.error(f"Failed to create snapshot for {dataset}: {snapshot_result.get('error')}")
            
            if not snapshots_created:
                await self._update_job_status(job_id, "failed", "No snapshots created")
                return
            
            # Phase 2: Mount snapshots and backup with Restic
            await self._update_job_status(job_id, "backing_up_data")
            
            backup_paths = []
            snapshot_mounts = []
            
            try:
                # Create temporary mount points for snapshots
                for snapshot in snapshots_created:
                    mount_point = f"/tmp/backup_mount_{job_id}_{len(snapshot_mounts)}"
                    os.makedirs(mount_point, exist_ok=True)
                    
                    # Mount snapshot (simplified - in production would use proper ZFS mounting)
                    backup_paths.append(mount_point)
                    snapshot_mounts.append(mount_point)
                
                # Perform Restic backup
                restic_result = await self.restic_manager.backup_paths(
                    config["repository"],
                    backup_paths,
                    tags=[f"job:{job_id}", f"name:{config['name']}"],
                    exclude=config.get("exclude", [])
                )
                
                if restic_result["success"]:
                    await self._update_job_status(job_id, "completed", None, {
                        "snapshots_created": len(snapshots_created),
                        "backup_stats": restic_result.get("stats", {}),
                        "snapshots": [s["snapshot_path"] for s in snapshots_created]
                    })
                    
                    # Broadcast completion
                    await websocket_manager.connection_manager.broadcast_to_channel(
                        "backups",
                        {
                            "type": "backup_completed",
                            "job_id": job_id,
                            "stats": restic_result.get("stats", {})
                        }
                    )
                else:
                    await self._update_job_status(job_id, "failed", restic_result.get("error"))
                    
            finally:
                # Cleanup mount points
                for mount_point in snapshot_mounts:
                    try:
                        if os.path.exists(mount_point):
                            shutil.rmtree(mount_point)
                    except Exception as e:
                        logger.error(f"Failed to cleanup mount point {mount_point}: {e}")
            
            # Phase 3: Cleanup old snapshots based on retention policy
            await self._cleanup_old_snapshots(config)
            
        except Exception as e:
            logger.error(f"Hybrid backup job {job_id} failed: {e}")
            await self._update_job_status(job_id, "failed", str(e))
        finally:
            # Remove job from active jobs
            if job_id in self.backup_jobs:
                del self.backup_jobs[job_id]
    
    async def _update_job_status(self, job_id: str, status: str, error: str = None, 
                               result: Dict[str, Any] = None):
        """Update backup job status"""
        try:
            job_info = await cache_manager.get(f"backup_job:{job_id}") or {}
            job_info.update({
                "status": status,
                "updated_at": datetime.now().isoformat(),
                "error": error,
                "result": result
            })
            
            await cache_manager.set(f"backup_job:{job_id}", job_info, ttl=3600)
            
        except Exception as e:
            logger.error(f"Failed to update job status for {job_id}: {e}")
    
    async def _cleanup_old_snapshots(self, config: Dict[str, Any]):
        """Cleanup old snapshots based on retention policy"""
        try:
            retention_days = config.get("retention", {}).get("days", 7)
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            for dataset in config["datasets"]:
                snapshots = await self.zfs_manager.list_snapshots(dataset)
                
                for snapshot in snapshots:
                    # Parse creation date and check if it's older than retention
                    # This is simplified - would need proper date parsing in production
                    snapshot_name = snapshot["snapshot"]
                    if snapshot_name.startswith("backup-"):
                        # Delete old backup snapshots
                        await self.zfs_manager.delete_snapshot(snapshot["name"])
                        
        except Exception as e:
            logger.error(f"Failed to cleanup old snapshots: {e}")
    
    async def get_backup_status(self, job_id: str) -> Dict[str, Any]:
        """Get backup job status"""
        try:
            job_info = await cache_manager.get(f"backup_job:{job_id}")
            if job_info:
                return job_info
            else:
                return {
                    "success": False,
                    "error": "Job not found",
                    "job_id": job_id
                }
                
        except Exception as e:
            logger.error(f"Failed to get backup status for {job_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id
            }
    
    async def list_active_jobs(self) -> List[Dict[str, Any]]:
        """List all active backup jobs"""
        try:
            active_jobs = []
            for job_id in self.backup_jobs.keys():
                job_info = await cache_manager.get(f"backup_job:{job_id}")
                if job_info:
                    active_jobs.append(job_info)
            
            return active_jobs
            
        except Exception as e:
            logger.error(f"Failed to list active backup jobs: {e}")
            return []


# Global backup service instance
hybrid_backup_service = HybridBackupService()