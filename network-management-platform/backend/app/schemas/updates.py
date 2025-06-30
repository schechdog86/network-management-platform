"""
Update Management Schemas
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UpdateStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RolloutStrategy(str, Enum):
    IMMEDIATE = "immediate"
    CANARY = "canary"
    STAGED = "staged"
    MANUAL = "manual"


class SnapInfo(BaseModel):
    """Snap information"""
    name: str
    channel: str
    current_revision: str
    available_revision: Optional[str] = None
    size_bytes: Optional[int] = None
    update_available: bool = False


class UpdateRequest(BaseModel):
    """Request to install updates"""
    snap_names: List[str] = Field(..., description="List of snaps to update")
    channel: Optional[str] = Field(None, description="Channel to update to")
    force: bool = Field(False, description="Force update even if workload is active")


class UpdateResponse(BaseModel):
    """Response from update installation"""
    node_id: str
    snap_names: List[str]
    status: UpdateStatus
    change_id: Optional[str] = None
    message: str


class FleetUpdateRequest(BaseModel):
    """Request for fleet-wide update"""
    node_ids: List[str] = Field(..., description="List of node IDs to update")
    snap_names: List[str] = Field(..., description="List of snaps to update")
    rollout_strategy: RolloutStrategy = Field(RolloutStrategy.CANARY, description="Rollout strategy")
    canary_percentage: int = Field(10, ge=1, le=50, description="Percentage of nodes for canary deployment")
    batch_size: int = Field(10, ge=1, description="Number of nodes to update in each batch")
    delay_between_batches: int = Field(300, ge=0, description="Delay between batches in seconds")
    max_failures: int = Field(5, ge=0, description="Maximum failures before stopping rollout")


class FleetUpdateResponse(BaseModel):
    """Response from fleet update"""
    update_id: str
    total_nodes: int
    rollout_strategy: RolloutStrategy
    status: str
    created_at: datetime


class NodeUpdateStatus(BaseModel):
    """Update status for a single node"""
    node_id: str
    last_check: Optional[datetime] = None
    last_update: Optional[datetime] = None
    available_updates: List[SnapInfo] = []
    current_status: UpdateStatus
    workload_status: str
    gpu_utilization: Optional[float] = None
    update_window_active: bool = False
    auto_update_enabled: bool = True
    error_message: Optional[str] = None


class UpdatePolicy(BaseModel):
    """Update policy configuration"""
    auto_update_enabled: bool = Field(True, description="Enable automatic updates")
    update_window_start: str = Field("02:00", description="Start of update window (HH:MM)")
    update_window_end: str = Field("06:00", description="End of update window (HH:MM)")
    max_gpu_utilization: float = Field(10.0, ge=0.0, le=100.0, description="Max GPU utilization % to allow updates")
    min_idle_time: int = Field(300, ge=0, description="Minimum idle time in seconds before update")
    enable_canary_updates: bool = Field(True, description="Enable canary updates")
    rollback_on_failure: bool = Field(True, description="Auto-rollback on failure")
    update_check_interval: int = Field(3600, ge=300, description="Update check interval in seconds")
    defer_during_training: bool = Field(True, description="Defer updates during AI training")
    
    @validator('update_window_start', 'update_window_end')
    def validate_time_format(cls, v):
        try:
            # Validate HH:MM format
            hour, minute = v.split(':')
            hour = int(hour)
            minute = int(minute)
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError('Invalid time')
            return v
        except:
            raise ValueError('Time must be in HH:MM format')


class SnapSchedule(BaseModel):
    """Schedule for a specific snap"""
    channel: str = Field("stable", description="Snap channel")
    hold: bool = Field(False, description="Hold updates for this snap")
    priority: str = Field("medium", description="Update priority (low, medium, high)")
    max_revisions_behind: int = Field(5, ge=1, description="Maximum revisions behind before forcing update")


class UpdateSchedule(BaseModel):
    """Update schedule configuration"""
    snaps: Dict[str, SnapSchedule] = Field(default_factory=dict, description="Per-snap schedules")
    maintenance_windows: List[str] = Field(default_factory=list, description="Maintenance window schedules")
    blackout_periods: List[str] = Field(default_factory=list, description="Blackout periods (no updates)")


class UpdateHistoryItem(BaseModel):
    """Single update history item"""
    timestamp: datetime
    snap_name: str
    action: str  # update, rollback, install, remove
    from_revision: Optional[str] = None
    to_revision: Optional[str] = None
    status: UpdateStatus
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None


class UpdateHistoryResponse(BaseModel):
    """Update history response"""
    node_id: str
    history: List[UpdateHistoryItem]
    total_count: int


class FleetUpdateStatus(BaseModel):
    """Status of fleet-wide update"""
    update_id: str
    rollout_strategy: RolloutStrategy
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    pending_nodes: int
    current_batch: int
    total_batches: int
    status: str  # running, completed, failed, cancelled
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    node_statuses: List[NodeUpdateStatus] = []


class WorkloadInfo(BaseModel):
    """Current workload information"""
    status: str  # idle, training, inference, maintenance
    gpu_utilization: float
    active_tasks: int
    running_actors: int
    estimated_completion_time: Optional[datetime] = None


class HealthCheckResult(BaseModel):
    """Health check result after update"""
    snap_name: str
    checks_passed: int
    checks_failed: int
    overall_status: str  # healthy, degraded, unhealthy
    details: List[str] = []
    timestamp: datetime


class UpdateMetrics(BaseModel):
    """Update metrics and statistics"""
    node_id: str
    total_updates: int
    successful_updates: int
    failed_updates: int
    rollbacks: int
    average_update_time: float
    last_successful_update: Optional[datetime] = None
    last_failed_update: Optional[datetime] = None
    uptime_percentage: float


class EmergencyStopRequest(BaseModel):
    """Emergency stop request"""
    reason: str = Field(..., description="Reason for emergency stop")
    affect_running_only: bool = Field(True, description="Only stop running updates, not scheduled ones")


class UpdateNotification(BaseModel):
    """Update notification for WebSocket"""
    type: str
    node_id: Optional[str] = None
    update_id: Optional[str] = None
    snap_name: Optional[str] = None
    status: Optional[UpdateStatus] = None
    message: str
    timestamp: datetime
    severity: str = "info"  # info, warning, error