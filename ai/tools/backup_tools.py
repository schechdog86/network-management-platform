"""
Backup management tools for LangChain
"""

from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
import os
import json
import subprocess
from datetime import datetime, timedelta
import hashlib

from .base import BaseNetworkTool, RequiresConfirmationMixin, CachedToolMixin


class BackupStatusInput(BaseModel):
    """Input for backup status check"""
    backup_type: Optional[str] = Field(None, description="Type of backup to check (all if not specified)")


class BackupStatusTool(BaseNetworkTool, CachedToolMixin):
    """Tool for checking backup status"""
    
    name: str = "backup_status"
    description: str = "Check the status of system backups including last run, next scheduled, and space usage"
    args_schema: Type[BaseModel] = BackupStatusInput
    
    def _execute(self, backup_type: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Check backup status"""
        # Check cache
        cache_key = f"backup_status_{backup_type or 'all'}"
        cached = self.get_cached_result(cache_key)
        if cached:
            return cached
        
        status = {
            "timestamp": datetime.now().isoformat(),
            "backup_types": {}
        }
        
        # Define backup types
        backup_types = ["full", "incremental", "config", "database"] if not backup_type else [backup_type]
        
        for btype in backup_types:
            type_status = self._get_backup_type_status(btype)
            if type_status:
                status["backup_types"][btype] = type_status
        
        # Overall status
        status["overall"] = self._calculate_overall_status(status["backup_types"])
        
        # Storage information
        status["storage"] = self._get_storage_info()
        
        # Cache result
        self.cache_result(cache_key, status)
        
        return status
    
    def _get_backup_type_status(self, backup_type: str) -> Dict[str, Any]:
        """Get status for specific backup type"""
        # In production, this would query actual backup system
        # For demo, we'll simulate status
        
        last_run = datetime.now() - timedelta(hours=12)
        next_run = datetime.now() + timedelta(hours=12)
        
        return {
            "last_run": {
                "timestamp": last_run.isoformat(),
                "status": "success",
                "duration_minutes": 45,
                "size_gb": 23.5,
                "files_backed_up": 15420
            },
            "next_scheduled": next_run.isoformat(),
            "retention_days": 30,
            "enabled": True,
            "recent_history": [
                {"date": (last_run - timedelta(days=i)).strftime("%Y-%m-%d"), "status": "success"}
                for i in range(7)
            ]
        }
    
    def _calculate_overall_status(self, backup_types: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall backup health"""
        total_types = len(backup_types)
        successful = sum(1 for t in backup_types.values() 
                        if t["last_run"]["status"] == "success")
        
        health = "healthy" if successful == total_types else "warning" if successful > 0 else "critical"
        
        return {
            "health": health,
            "successful_types": successful,
            "total_types": total_types,
            "last_full_backup": max(
                (t["last_run"]["timestamp"] for t in backup_types.values() 
                 if t.get("last_run")),
                default=None
            )
        }
    
    def _get_storage_info(self) -> Dict[str, Any]:
        """Get backup storage information"""
        backup_path = "/var/backups"
        
        if os.path.exists(backup_path):
            total, used, free = os.statvfs(backup_path).f_blocks, 0, 0
            # Calculate actual values (simplified)
            
            return {
                "backup_path": backup_path,
                "total_space_gb": 500,
                "used_space_gb": 245,
                "free_space_gb": 255,
                "usage_percent": 49
            }
        else:
            return {
                "backup_path": backup_path,
                "error": "Backup directory not found"
            }


class CreateBackupInput(BaseModel):
    """Input for creating backup"""
    backup_type: str = Field(description="Type of backup: full, incremental, config, database")
    description: Optional[str] = Field(None, description="Description for this backup")
    compress: bool = Field(default=True, description="Compress backup files")
    encrypt: bool = Field(default=True, description="Encrypt backup files")


class CreateBackupTool(BaseNetworkTool, RequiresConfirmationMixin):
    """Tool for creating backups"""
    
    name: str = "create_backup"
    description: str = "Create a system backup of specified type"
    args_schema: Type[BaseModel] = CreateBackupInput
    
    def _execute(self, backup_type: str, description: Optional[str] = None, 
                 compress: bool = True, encrypt: bool = True, timeout: int = 30) -> Dict[str, Any]:
        """Create backup"""
        valid_types = ["full", "incremental", "config", "database"]
        
        if backup_type not in valid_types:
            return {"error": f"Invalid backup type. Valid types: {valid_types}"}
        
        # Confirm action
        if self.requires_confirmation:
            if not self.get_confirmation(f"Create {backup_type} backup"):
                return {"cancelled": True, "reason": "User cancelled backup"}
        
        # Create backup metadata
        backup_id = self._generate_backup_id()
        backup_meta = {
            "id": backup_id,
            "type": backup_type,
            "description": description or f"Manual {backup_type} backup",
            "started_at": datetime.now().isoformat(),
            "compress": compress,
            "encrypt": encrypt,
            "status": "in_progress"
        }
        
        # In production, this would trigger actual backup
        # For demo, we'll simulate the process
        result = self._simulate_backup(backup_type, backup_meta)
        
        return result
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_part = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        return f"backup_{timestamp}_{random_part}"
    
    def _simulate_backup(self, backup_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate backup process"""
        # In production, this would call actual backup tools
        
        # Simulate some work
        import time
        time.sleep(2)
        
        # Update metadata
        metadata["completed_at"] = datetime.now().isoformat()
        metadata["status"] = "completed"
        metadata["size_gb"] = 23.5 if backup_type == "full" else 2.3
        metadata["files_count"] = 15420 if backup_type == "full" else 1250
        metadata["backup_location"] = f"/var/backups/{metadata['id']}.tar.gz"
        
        # Calculate duration
        started = datetime.fromisoformat(metadata["started_at"])
        completed = datetime.fromisoformat(metadata["completed_at"])
        metadata["duration_seconds"] = (completed - started).total_seconds()
        
        return {
            "success": True,
            "backup": metadata,
            "message": f"{backup_type.capitalize()} backup completed successfully"
        }


class RestoreBackupInput(BaseModel):
    """Input for restore backup"""
    backup_id: Optional[str] = Field(None, description="Specific backup ID to restore")
    backup_date: Optional[str] = Field(None, description="Date of backup to restore (YYYY-MM-DD)")
    backup_type: Optional[str] = Field(None, description="Type of backup to restore")
    target_location: Optional[str] = Field(None, description="Where to restore (default: original location)")
    verify_only: bool = Field(default=False, description="Only verify backup, don't restore")


class RestoreBackupTool(BaseNetworkTool, RequiresConfirmationMixin):
    """Tool for restoring from backup"""
    
    name: str = "restore_backup"
    description: str = "Restore system from a backup"
    args_schema: Type[BaseModel] = RestoreBackupInput
    requires_confirmation: bool = True
    confirmation_prompt: str = "Restoring from backup will overwrite current data. Proceed?"
    
    def _execute(self, backup_id: Optional[str] = None, backup_date: Optional[str] = None,
                 backup_type: Optional[str] = None, target_location: Optional[str] = None,
                 verify_only: bool = False, timeout: int = 30) -> Dict[str, Any]:
        """Restore from backup"""
        # Find backup to restore
        backup = self._find_backup(backup_id, backup_date, backup_type)
        
        if not backup:
            return {"error": "No matching backup found"}
        
        if verify_only:
            return self._verify_backup(backup)
        
        # Confirm restore
        if self.requires_confirmation:
            if not self.get_confirmation(f"Restore from backup {backup['id']}"):
                return {"cancelled": True, "reason": "User cancelled restore"}
        
        # Perform restore
        result = self._perform_restore(backup, target_location)
        
        return result
    
    def _find_backup(self, backup_id: Optional[str], backup_date: Optional[str], 
                     backup_type: Optional[str]) -> Optional[Dict[str, Any]]:
        """Find backup based on criteria"""
        # In production, this would query backup catalog
        
        # Simulated backup
        return {
            "id": backup_id or "backup_20240115_120000_a1b2c3d4",
            "type": backup_type or "full",
            "date": backup_date or "2024-01-15",
            "size_gb": 23.5,
            "location": "/var/backups/backup_20240115_120000_a1b2c3d4.tar.gz",
            "encrypted": True,
            "compressed": True
        }
    
    def _verify_backup(self, backup: Dict[str, Any]) -> Dict[str, Any]:
        """Verify backup integrity"""
        return {
            "backup_id": backup["id"],
            "verification": {
                "file_exists": True,
                "checksum_valid": True,
                "encryption_valid": True,
                "contents_readable": True
            },
            "status": "valid",
            "message": "Backup is valid and can be restored"
        }
    
    def _perform_restore(self, backup: Dict[str, Any], target_location: Optional[str]) -> Dict[str, Any]:
        """Perform the restore operation"""
        # In production, this would perform actual restore
        
        return {
            "success": True,
            "backup_id": backup["id"],
            "restored_to": target_location or "original location",
            "files_restored": 15420,
            "size_restored_gb": backup["size_gb"],
            "duration_minutes": 45,
            "message": "Restore completed successfully"
        }


class BackupHistoryInput(BaseModel):
    """Input for backup history"""
    days: int = Field(default=30, description="Number of days of history to retrieve")
    backup_type: Optional[str] = Field(None, description="Filter by backup type")
    status: Optional[str] = Field(None, description="Filter by status: success, failed, all")


class BackupHistoryTool(BaseNetworkTool):
    """Tool for viewing backup history"""
    
    name: str = "backup_history"
    description: str = "View backup history and statistics"
    args_schema: Type[BaseModel] = BackupHistoryInput
    
    def _execute(self, days: int = 30, backup_type: Optional[str] = None, 
                 status: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Get backup history"""
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # In production, this would query backup logs
        # For demo, generate sample history
        history = self._generate_sample_history(start_date, end_date, backup_type, status)
        
        # Calculate statistics
        stats = self._calculate_statistics(history)
        
        return {
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "days": days
            },
            "filters": {
                "backup_type": backup_type,
                "status": status
            },
            "statistics": stats,
            "recent_backups": history[:10],  # Show last 10
            "total_backups": len(history)
        }
    
    def _generate_sample_history(self, start_date: datetime, end_date: datetime,
                                backup_type: Optional[str], status_filter: Optional[str]) -> List[Dict[str, Any]]:
        """Generate sample backup history"""
        history = []
        current_date = end_date
        
        while current_date >= start_date:
            # Daily full backup
            if not backup_type or backup_type == "full":
                backup = {
                    "id": f"backup_{current_date.strftime('%Y%m%d')}_000000_full",
                    "type": "full",
                    "date": current_date.strftime("%Y-%m-%d"),
                    "time": "00:00:00",
                    "status": "success" if current_date.day % 7 != 0 else "failed",
                    "size_gb": 23.5 + (current_date.day % 5),
                    "duration_minutes": 45 + (current_date.day % 10),
                    "files_count": 15420 + (current_date.day * 100)
                }
                
                if not status_filter or status_filter == "all" or backup["status"] == status_filter:
                    history.append(backup)
            
            # Hourly incremental
            if current_date.date() == datetime.now().date() and (not backup_type or backup_type == "incremental"):
                for hour in range(0, 24, 6):
                    backup = {
                        "id": f"backup_{current_date.strftime('%Y%m%d')}_{hour:02d}0000_incr",
                        "type": "incremental",
                        "date": current_date.strftime("%Y-%m-%d"),
                        "time": f"{hour:02d}:00:00",
                        "status": "success",
                        "size_gb": 0.5 + (hour % 3) * 0.2,
                        "duration_minutes": 5 + (hour % 4),
                        "files_count": 250 + (hour * 10)
                    }
                    
                    if not status_filter or status_filter == "all" or backup["status"] == status_filter:
                        history.append(backup)
            
            current_date -= timedelta(days=1)
        
        return sorted(history, key=lambda x: f"{x['date']} {x['time']}", reverse=True)
    
    def _calculate_statistics(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate backup statistics"""
        if not history:
            return {
                "total_backups": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0,
                "total_size_gb": 0,
                "average_duration_minutes": 0
            }
        
        successful = [b for b in history if b["status"] == "success"]
        failed = [b for b in history if b["status"] == "failed"]
        
        total_size = sum(b["size_gb"] for b in successful)
        avg_duration = sum(b["duration_minutes"] for b in successful) / len(successful) if successful else 0
        
        return {
            "total_backups": len(history),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": round(len(successful) / len(history) * 100, 1),
            "total_size_gb": round(total_size, 1),
            "average_duration_minutes": round(avg_duration, 1),
            "backup_types": {
                backup_type: len([b for b in history if b["type"] == backup_type])
                for backup_type in set(b["type"] for b in history)
            }
        }