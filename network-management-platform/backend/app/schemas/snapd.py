"""
Snapd Management Schemas
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


class SnapOperation(str, Enum):
    INSTALL = "install"
    REFRESH = "refresh"
    REMOVE = "remove"
    REVERT = "revert"
    ENABLE = "enable"
    DISABLE = "disable"


class SnapStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    AVAILABLE = "available"
    BROKEN = "broken"


class ChangeStatus(str, Enum):
    DO = "Do"
    DOING = "Doing"
    DONE = "Done"
    ABORT = "Abort"
    HOLD = "Hold"
    ERROR = "Error"
    WAIT = "Wait"


class DeviceRegistrationRequest(BaseModel):
    """Request to register a device for snapd management"""
    endpoint: str = Field(..., description="Snapd endpoint (URL or Unix socket path)")
    auth_token: Optional[str] = Field(None, description="Authentication token for snapd access")
    
    @validator('endpoint')
    def validate_endpoint(cls, v):
        if not v:
            raise ValueError('Endpoint cannot be empty')
        if not (v.startswith('http://') or v.startswith('https://') or 
                v.startswith('/') or v.startswith('unix://')):
            raise ValueError('Invalid endpoint format')
        return v


class DeviceRegistrationResponse(BaseModel):
    """Response from device registration"""
    device_id: str
    endpoint: str
    system_info: Dict[str, Any]
    registered_at: datetime
    status: str


class DeviceSystemInfoResponse(BaseModel):
    """Device system information response"""
    device_id: str
    system_info: Dict[str, Any]
    timestamp: datetime


class SnapInstallRequest(BaseModel):
    """Request to install a snap"""
    snap_name: str = Field(..., description="Name of the snap to install")
    channel: Optional[str] = Field(None, description="Snap channel (stable, beta, edge, etc.)")
    classic: bool = Field(False, description="Install in classic confinement")
    dangerous: bool = Field(False, description="Install unsigned snap")
    
    @validator('snap_name')
    def validate_snap_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Snap name cannot be empty')
        # Basic snap name validation (letters, numbers, hyphens)
        import re
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', v):
            raise ValueError('Invalid snap name format')
        return v.strip()


class SnapInstallResponse(BaseModel):
    """Response from snap installation"""
    device_id: str
    snap_name: str
    change_id: str
    channel: Optional[str]
    status: str
    timestamp: datetime


class SnapRefreshRequest(BaseModel):
    """Request to refresh a snap"""
    snap_name: str = Field(..., description="Name of the snap to refresh")
    channel: Optional[str] = Field(None, description="Channel to refresh to")
    
    @validator('snap_name')
    def validate_snap_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Snap name cannot be empty')
        return v.strip()


class SnapRefreshResponse(BaseModel):
    """Response from snap refresh"""
    device_id: str
    snap_name: str
    change_id: str
    channel: Optional[str]
    status: str
    timestamp: datetime


class SnapRemoveRequest(BaseModel):
    """Request to remove a snap"""
    snap_name: str = Field(..., description="Name of the snap to remove")
    purge: bool = Field(False, description="Purge snap data")
    
    @validator('snap_name')
    def validate_snap_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Snap name cannot be empty')
        return v.strip()


class SnapRemoveResponse(BaseModel):
    """Response from snap removal"""
    device_id: str
    snap_name: str
    change_id: str
    purge: bool
    status: str
    timestamp: datetime


class SnapInfoResponse(BaseModel):
    """Response with snap information"""
    device_id: str
    snap_name: str
    version: str
    revision: str
    status: str
    channel: str
    installed_size: Optional[int]
    install_date: Optional[datetime]
    summary: Optional[str]
    description: Optional[str]
    developer: Optional[str]
    contact: Optional[str]
    website: Optional[str]
    license: Optional[str]
    tracking_channel: Optional[str]
    refresh_date: Optional[datetime]
    cohort_key: Optional[str]
    timestamp: datetime


class SnapData(BaseModel):
    """Individual snap data"""
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
    tracking_channel: Optional[str] = None
    refresh_date: Optional[datetime] = None


class SnapListResponse(BaseModel):
    """Response with list of snaps"""
    device_id: str
    snaps: List[SnapData]
    total_count: int
    timestamp: datetime


class TaskData(BaseModel):
    """Individual task data"""
    id: Optional[str]
    kind: Optional[str]
    summary: Optional[str]
    status: Optional[str]
    progress: Optional[Dict[str, Any]] = {}


class SnapChangeResponse(BaseModel):
    """Response with snap change information"""
    device_id: str
    change_id: str
    kind: str
    summary: str
    status: str
    ready: bool
    spawn_time: datetime
    ready_time: Optional[datetime]
    error: Optional[str]
    tasks: List[TaskData]
    timestamp: datetime


class InterfaceConnectionRequest(BaseModel):
    """Request to connect/disconnect snap interfaces"""
    plug: str = Field(..., description="Plug specification (snap:plug)")
    slot: str = Field(..., description="Slot specification (snap:slot)")
    
    @validator('plug', 'slot')
    def validate_interface_spec(cls, v):
        if not v or ':' not in v:
            raise ValueError('Interface specification must be in format "snap:interface"')
        return v


class InterfaceConnectionResponse(BaseModel):
    """Response from interface connection operation"""
    device_id: str
    plug: str
    slot: str
    change_id: str
    action: str  # "connect" or "disconnect"
    status: str
    timestamp: datetime


class BulkSnapOperationRequest(BaseModel):
    """Request for bulk snap operations"""
    operation: SnapOperation = Field(..., description="Operation to perform")
    device_ids: List[str] = Field(..., description="List of device IDs")
    snap_names: List[str] = Field(..., description="List of snap names")
    channel: Optional[str] = Field(None, description="Channel for install/refresh operations")
    classic: bool = Field(False, description="Classic confinement for install operations")
    dangerous: bool = Field(False, description="Dangerous install for install operations")
    purge: bool = Field(False, description="Purge data for remove operations")
    
    @validator('device_ids')
    def validate_device_ids(cls, v):
        if not v:
            raise ValueError('At least one device ID must be specified')
        return v
    
    @validator('snap_names')
    def validate_snap_names(cls, v):
        if not v:
            raise ValueError('At least one snap name must be specified')
        return v


class BulkOperationResult(BaseModel):
    """Result of a single operation in bulk request"""
    device_id: str
    snap_name: str
    change_id: Optional[str]
    status: str  # "started", "failed"
    error: Optional[str]


class BulkSnapOperationResponse(BaseModel):
    """Response from bulk snap operation"""
    operation_id: str
    operation: SnapOperation
    total_operations: int
    successful_operations: int
    failed_operations: int
    results: List[BulkOperationResult]
    timestamp: datetime


class SnapHealth(BaseModel):
    """Snap health information"""
    name: str
    status: str
    services_active: int
    services_total: int
    last_refresh: Optional[datetime]
    errors: List[str] = []


class DeviceSnapHealth(BaseModel):
    """Overall snap health for a device"""
    device_id: str
    total_snaps: int
    active_snaps: int
    broken_snaps: int
    snap_health: List[SnapHealth]
    system_health: str
    timestamp: datetime


class SnapSearchRequest(BaseModel):
    """Request to search for snaps in the store"""
    query: str = Field(..., description="Search query")
    category: Optional[str] = Field(None, description="Category filter")
    private: bool = Field(False, description="Include private snaps")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Search query cannot be empty')
        return v.strip()


class SnapSearchResult(BaseModel):
    """Individual snap search result"""
    name: str
    version: str
    summary: str
    description: str
    developer: str
    publisher: Dict[str, Any]
    channels: Dict[str, Any]
    website: Optional[str]
    contact: Optional[str]
    license: Optional[str]
    price: Optional[str]


class SnapSearchResponse(BaseModel):
    """Response from snap search"""
    query: str
    results: List[SnapSearchResult]
    total_count: int
    timestamp: datetime


class SnapValidationSet(BaseModel):
    """Snap validation set configuration"""
    account_id: str
    name: str
    sequence: int
    snaps: List[Dict[str, Any]]
    timestamp: datetime


class DeviceConfiguration(BaseModel):
    """Device configuration for snap management"""
    device_id: str
    auto_refresh: bool = True
    refresh_schedule: Optional[str] = None
    validation_sets: List[str] = []
    hold_snaps: List[str] = []
    proxy_settings: Optional[Dict[str, str]] = None
    experimental_features: List[str] = []


class SnapMetrics(BaseModel):
    """Snap usage metrics"""
    device_id: str
    snap_name: str
    cpu_usage: float
    memory_usage: int
    disk_usage: int
    network_usage: Dict[str, int]
    active_connections: int
    uptime_seconds: int
    timestamp: datetime


class FleetSnapStatus(BaseModel):
    """Fleet-wide snap status summary"""
    snap_name: str
    total_devices: int
    installed_devices: int
    active_devices: int
    version_distribution: Dict[str, int]
    channel_distribution: Dict[str, int]
    error_count: int
    last_update: Optional[datetime]


class SnapOperationHistory(BaseModel):
    """Historical snap operation record"""
    device_id: str
    operation_id: str
    operation: SnapOperation
    snap_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    user_id: Optional[str]