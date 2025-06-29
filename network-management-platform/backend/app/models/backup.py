"""
Database models for backup management
"""

from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid
from enum import Enum

from app.core.database import Base


class BackupType(str, Enum):
    ZFS_SNAPSHOT = "zfs_snapshot"
    RESTIC_BACKUP = "restic_backup"
    HYBRID_BACKUP = "hybrid_backup"
    MANUAL_BACKUP = "manual_backup"


class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackupJob(Base):
    """Backup job tracking"""
    __tablename__ = "backup_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # BackupType enum
    status = Column(String(50), nullable=False, default=BackupStatus.PENDING)
    
    # Configuration
    config = Column(JSON, nullable=False)  # Backup configuration (datasets, repository, etc.)
    
    # Timing
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Progress and results
    progress_percent = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)  # Backup statistics and results
    
    # Resource usage
    bytes_processed = Column(Integer, default=0)
    bytes_backed_up = Column(Integer, default=0)
    files_processed = Column(Integer, default=0)
    
    # Metadata
    created_by = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags for organization


class BackupRepository(Base):
    """Backup repository configuration"""
    __tablename__ = "backup_repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    type = Column(String(50), nullable=False)  # restic, zfs, etc.
    
    # Repository details
    path = Column(String(1024), nullable=False)
    encrypted = Column(Boolean, default=True)
    compression_enabled = Column(Boolean, default=True)
    
    # Configuration
    config = Column(JSON, nullable=False)  # Repository-specific configuration
    
    # Status
    active = Column(Boolean, default=True)
    last_checked = Column(DateTime, nullable=True)
    health_status = Column(String(50), default="unknown")
    
    # Statistics
    total_size = Column(Integer, default=0)
    total_snapshots = Column(Integer, default=0)
    last_backup = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BackupSnapshot(Base):
    """Individual backup snapshots/archives"""
    __tablename__ = "backup_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=True)  # Associated backup job
    
    # Snapshot identification
    snapshot_id = Column(String(255), nullable=False)  # Restic snapshot ID or ZFS snapshot name
    name = Column(String(255), nullable=True)
    
    # Content information
    paths = Column(JSON, nullable=False)  # List of backed up paths
    hostname = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    
    # Statistics
    size = Column(Integer, default=0)
    files_count = Column(Integer, default=0)
    directories_count = Column(Integer, default=0)
    
    # Timing
    created_at = Column(DateTime, server_default=func.now())
    backup_time = Column(DateTime, nullable=False)  # When the backup was actually taken
    
    # Metadata
    tags = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Additional snapshot metadata


class BackupSchedule(Base):
    """Backup scheduling configuration"""
    __tablename__ = "backup_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    
    # Schedule configuration
    cron_expression = Column(String(255), nullable=False)
    timezone = Column(String(50), default="UTC")
    enabled = Column(Boolean, default=True)
    
    # Backup configuration
    backup_config = Column(JSON, nullable=False)  # Backup job configuration
    repository_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Retention policy
    retention_policy = Column(JSON, nullable=False)  # Retention rules
    
    # Status
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    last_status = Column(String(50), nullable=True)
    
    # Statistics
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BackupRetentionPolicy(Base):
    """Backup retention policies"""
    __tablename__ = "backup_retention_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Retention rules
    keep_daily = Column(Integer, default=7)      # Keep daily backups for 7 days
    keep_weekly = Column(Integer, default=4)     # Keep weekly backups for 4 weeks
    keep_monthly = Column(Integer, default=12)   # Keep monthly backups for 12 months
    keep_yearly = Column(Integer, default=3)     # Keep yearly backups for 3 years
    
    # Advanced retention
    keep_within = Column(String(50), nullable=True)  # Keep all backups within timeframe (e.g., "30d")
    keep_last = Column(Integer, nullable=True)       # Keep last N backups regardless of age
    
    # Policy configuration
    policy_config = Column(JSON, nullable=True)  # Additional policy rules
    
    # Status
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BackupVerification(Base):
    """Backup verification results"""
    __tablename__ = "backup_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Verification details
    verification_type = Column(String(50), nullable=False)  # integrity, restore_test, etc.
    status = Column(String(50), nullable=False)
    
    # Results
    files_checked = Column(Integer, default=0)
    files_valid = Column(Integer, default=0)
    files_corrupted = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Details
    error_message = Column(Text, nullable=True)
    verification_data = Column(JSON, nullable=True)  # Detailed verification results
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())