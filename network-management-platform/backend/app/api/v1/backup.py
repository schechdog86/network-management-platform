"""
Backup management API endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import logging

from app.core.database import get_db
from app.services.backup_service import hybrid_backup_service
from app.models.backup import BackupJob, BackupEvent, BackupStorage

router = APIRouter()
logger = logging.getLogger(__name__)


class BackupConfigRequest(BaseModel):
    """Backup configuration request"""
    name: str = Field(..., description="Backup job name")
    datasets: List[str] = Field(..., description="ZFS datasets to backup")
    repository: str = Field(..., description="Restic repository name")
    exclude: List[str] = Field(default=[], description="Exclude patterns")
    tags: List[str] = Field(default=[], description="Backup tags")
    retention: dict = Field(default={"days": 7}, description="Retention policy")


class RepositoryConfigRequest(BaseModel):
    """Repository configuration request"""
    name: str = Field(..., description="Repository name")
    type: str = Field(default="restic", description="Repository type")
    path: str = Field(..., description="Repository path")
    password: str = Field(..., description="Repository password")
    encrypted: bool = Field(default=True, description="Enable encryption")
    compression: bool = Field(default=True, description="Enable compression")


@router.post("/jobs")
async def create_backup_job(
    backup_config: BackupConfigRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Create a new backup job"""
    try:
        # Convert request to internal config format
        config = {
            "name": backup_config.name,
            "datasets": backup_config.datasets,
            "repository": backup_config.repository,
            "exclude": backup_config.exclude,
            "tags": backup_config.tags,
            "retention": backup_config.retention
        }
        
        # Create hybrid backup
        result = await hybrid_backup_service.create_hybrid_backup(config)
        
        if result["success"]:
            return {
                "success": True,
                "job_id": result["job_id"],
                "name": result["name"],
                "status": result["status"],
                "message": result["message"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create backup job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create backup job")


@router.get("/jobs/{job_id}")
async def get_backup_job_status(job_id: str):
    """Get backup job status"""
    try:
        status = await hybrid_backup_service.get_backup_status(job_id)
        
        if "error" in status and status["error"] == "Job not found":
            raise HTTPException(status_code=404, detail="Backup job not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backup job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")


@router.get("/jobs")
async def list_backup_jobs():
    """List all active backup jobs"""
    try:
        jobs = await hybrid_backup_service.list_active_jobs()
        return {
            "jobs": jobs,
            "total": len(jobs)
        }
        
    except Exception as e:
        logger.error(f"Failed to list backup jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list backup jobs")


@router.post("/repositories")
async def create_repository(
    repo_config: RepositoryConfigRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create or initialize a new backup repository"""
    try:
        # Initialize Restic repository
        result = await hybrid_backup_service.restic_manager.init_repository(
            repo_config.name,
            repo_config.path,
            repo_config.password
        )
        
        if result["success"]:
            return {
                "success": True,
                "repository": result["repository"],
                "path": result["path"],
                "message": result["message"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create repository: {e}")
        raise HTTPException(status_code=500, detail="Failed to create repository")


@router.get("/repositories/{repo_name}/snapshots")
async def list_repository_snapshots(repo_name: str):
    """List snapshots in a repository"""
    try:
        snapshots = await hybrid_backup_service.restic_manager.list_snapshots(repo_name)
        
        return {
            "repository": repo_name,
            "snapshots": snapshots,
            "total": len(snapshots)
        }
        
    except Exception as e:
        logger.error(f"Failed to list repository snapshots: {e}")
        raise HTTPException(status_code=500, detail="Failed to list snapshots")


@router.post("/repositories/{repo_name}/check")
async def check_repository_integrity(repo_name: str):
    """Check repository integrity"""
    try:
        result = await hybrid_backup_service.restic_manager.check_repository(repo_name)
        
        return {
            "repository": repo_name,
            "success": result["success"],
            "output": result.get("output", ""),
            "error": result.get("error")
        }
        
    except Exception as e:
        logger.error(f"Failed to check repository: {e}")
        raise HTTPException(status_code=500, detail="Failed to check repository")


@router.post("/restore")
async def restore_backup(
    repo_name: str,
    snapshot_id: str,
    target_path: str,
    include_patterns: List[str] = None,
    background_tasks: BackgroundTasks = None
):
    """Restore backup from snapshot"""
    try:
        result = await hybrid_backup_service.restic_manager.restore_snapshot(
            repo_name=repo_name,
            snapshot_id=snapshot_id,
            target_path=target_path,
            include=include_patterns
        )
        
        return {
            "success": result["success"],
            "repository": result["repository"],
            "snapshot_id": result["snapshot_id"],
            "target_path": result["target_path"],
            "error": result.get("error")
        }
        
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore backup")


@router.get("/zfs/datasets")
async def list_zfs_datasets():
    """List available ZFS datasets"""
    try:
        # Get ZFS datasets
        result = await hybrid_backup_service.zfs_manager._run_command([
            "zfs", "list", "-H", "-o", "name,type,mountpoint,used,avail"
        ])
        
        if not result["success"]:
            return {"datasets": [], "error": result.get("error")}
        
        datasets = []
        for line in result["output"].strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 5:
                    datasets.append({
                        "name": parts[0],
                        "type": parts[1],
                        "mountpoint": parts[2],
                        "used": parts[3],
                        "available": parts[4]
                    })
        
        return {
            "datasets": datasets,
            "total": len(datasets)
        }
        
    except Exception as e:
        logger.error(f"Failed to list ZFS datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to list ZFS datasets")


@router.get("/zfs/snapshots")
async def list_zfs_snapshots(dataset: str = None):
    """List ZFS snapshots"""
    try:
        snapshots = await hybrid_backup_service.zfs_manager.list_snapshots(dataset)
        
        return {
            "dataset": dataset,
            "snapshots": snapshots,
            "total": len(snapshots)
        }
        
    except Exception as e:
        logger.error(f"Failed to list ZFS snapshots: {e}")
        raise HTTPException(status_code=500, detail="Failed to list ZFS snapshots")


@router.post("/zfs/snapshots")
async def create_zfs_snapshot(
    dataset: str,
    snapshot_name: str = None
):
    """Create ZFS snapshot"""
    try:
        result = await hybrid_backup_service.zfs_manager.create_snapshot(
            dataset=dataset,
            snapshot_name=snapshot_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to create ZFS snapshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ZFS snapshot")


@router.delete("/zfs/snapshots/{snapshot_path:path}")
async def delete_zfs_snapshot(snapshot_path: str):
    """Delete ZFS snapshot"""
    try:
        result = await hybrid_backup_service.zfs_manager.delete_snapshot(snapshot_path)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to delete ZFS snapshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete ZFS snapshot")


@router.get("/statistics")
async def get_backup_statistics():
    """Get backup system statistics"""
    try:
        # Get active jobs count
        active_jobs = await hybrid_backup_service.list_active_jobs()
        
        # Get ZFS snapshots count
        all_snapshots = await hybrid_backup_service.zfs_manager.list_snapshots()
        
        return {
            "active_jobs": len(active_jobs),
            "total_zfs_snapshots": len(all_snapshots),
            "repositories_configured": len(hybrid_backup_service.restic_manager.repositories),
            "backup_jobs": active_jobs,
            "recent_snapshots": all_snapshots[-10:] if all_snapshots else []
        }
        
    except Exception as e:
        logger.error(f"Failed to get backup statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get backup statistics")


@router.post("/test-configuration")
async def test_backup_configuration(backup_config: BackupConfigRequest):
    """Test backup configuration without executing"""
    try:
        # Validate datasets exist
        for dataset in backup_config.datasets:
            result = await hybrid_backup_service.zfs_manager._run_command([
                "zfs", "list", dataset
            ])
            if not result["success"]:
                return {
                    "valid": False,
                    "error": f"Dataset {dataset} not found",
                    "dataset": dataset
                }
        
        # Check if repository is configured
        if backup_config.repository not in hybrid_backup_service.restic_manager.repositories:
            return {
                "valid": False,
                "error": f"Repository {backup_config.repository} not configured"
            }
        
        return {
            "valid": True,
            "message": "Backup configuration is valid",
            "datasets": backup_config.datasets,
            "repository": backup_config.repository
        }
        
    except Exception as e:
        logger.error(f"Failed to test backup configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to test configuration")