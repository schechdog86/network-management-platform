"""
Pydantic schemas for device management
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, IPvAnyAddress, validator
from enum import Enum


class DeviceType(str, Enum):
    """Device type enumeration"""
    SERVER = "server"
    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    ACCESS_POINT = "access_point"
    WORKSTATION = "workstation"
    PRINTER = "printer"
    STORAGE = "storage"
    UNKNOWN = "unknown"


class DeviceStatus(str, Enum):
    """Device status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DeviceBase(BaseModel):
    """Base device schema"""
    hostname: str = Field(..., min_length=1, max_length=255)
    ip_address: IPvAnyAddress
    mac_address: Optional[str] = Field(None, regex=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    device_type: DeviceType = DeviceType.UNKNOWN
    manufacturer: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    os_info: Optional[Dict[str, Any]] = None
    hardware_specs: Optional[Dict[str, Any]] = None
    
    # Management configuration
    snmp_community: Optional[str] = Field(None, max_length=100)
    snmp_version: Optional[str] = Field(None, regex=r'^(1|2c|3)$')
    ssh_username: Optional[str] = Field(None, max_length=100)
    ssh_port: int = Field(22, ge=1, le=65535)
    
    # Monitoring settings
    monitoring_enabled: bool = True
    backup_enabled: bool = False
    
    # Metadata
    tags: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class DeviceCreate(DeviceBase):
    """Schema for creating a new device"""
    pass


class DeviceUpdate(BaseModel):
    """Schema for updating device information"""
    hostname: Optional[str] = Field(None, min_length=1, max_length=255)
    mac_address: Optional[str] = Field(None, regex=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    device_type: Optional[DeviceType] = None
    manufacturer: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    os_info: Optional[Dict[str, Any]] = None
    hardware_specs: Optional[Dict[str, Any]] = None
    
    # Management configuration
    snmp_community: Optional[str] = Field(None, max_length=100)
    snmp_version: Optional[str] = Field(None, regex=r'^(1|2c|3)$')
    ssh_username: Optional[str] = Field(None, max_length=100)
    ssh_port: Optional[int] = Field(None, ge=1, le=65535)
    
    # Monitoring settings
    monitoring_enabled: Optional[bool] = None
    backup_enabled: Optional[bool] = None
    
    # Metadata
    tags: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class DeviceResponse(DeviceBase):
    """Schema for device response"""
    id: str
    status: DeviceStatus = DeviceStatus.UNKNOWN
    last_seen: Optional[datetime] = None
    last_scan: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DeviceMetricBase(BaseModel):
    """Base device metric schema"""
    metric_type: str = Field(..., min_length=1, max_length=50)
    metric_name: str = Field(..., min_length=1, max_length=100)
    value: float
    unit: Optional[str] = Field(None, max_length=20)
    tags: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceMetricCreate(DeviceMetricBase):
    """Schema for creating device metrics"""
    device_id: str
    timestamp: Optional[datetime] = None


class DeviceMetricResponse(DeviceMetricBase):
    """Schema for device metric response"""
    id: str
    device_id: str
    timestamp: datetime
    
    class Config:
        from_attributes = True


class DeviceScanRequest(BaseModel):
    """Schema for network scan request"""
    subnets: List[str] = Field(..., min_items=1)
    port_range: str = Field("1-1024", regex=r'^\d+(-\d+)?$')
    scan_type: str = Field("standard", regex=r'^(standard|deep|fast)$')
    timeout: int = Field(30, ge=5, le=300)
    include_ports: bool = True
    include_os_detection: bool = True
    include_service_detection: bool = True
    
    @validator('subnets')
    def validate_subnets(cls, v):
        """Validate subnet format"""
        import ipaddress
        for subnet in v:
            try:
                ipaddress.ip_network(subnet, strict=False)
            except ValueError:
                raise ValueError(f"Invalid subnet format: {subnet}")
        return v


class DeviceScanResponse(BaseModel):
    """Schema for scan response"""
    scan_id: str
    status: str = Field(..., regex=r'^(pending|running|completed|failed)$')
    progress: float = Field(0.0, ge=0.0, le=100.0)
    devices_found: int = 0
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class DeviceStatusResponse(BaseModel):
    """Schema for real-time device status"""
    device_id: str
    status: DeviceStatus
    response_time: Optional[float] = None  # in milliseconds
    last_check: datetime
    services: Optional[List[Dict[str, Any]]] = None
    system_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class BulkActionRequest(BaseModel):
    """Schema for bulk device actions"""
    action: str = Field(..., regex=r'^(wake|reboot|scan|update_status|backup)$')
    device_ids: List[str] = Field(..., min_items=1, max_items=100)
    parameters: Optional[Dict[str, Any]] = None


class BulkActionResponse(BaseModel):
    """Schema for bulk action response"""
    action_id: str
    action: str
    device_count: int
    status: str = Field(..., regex=r'^(pending|running|completed|failed)$')
    progress: float = Field(0.0, ge=0.0, le=100.0)
    successful_devices: List[str] = []
    failed_devices: List[str] = []
    error_messages: Dict[str, str] = {}


class DevicePerformanceMetrics(BaseModel):
    """Schema for device performance metrics"""
    device_id: str
    timestamp: datetime
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    disk_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    network_rx_bytes: Optional[int] = Field(None, ge=0)
    network_tx_bytes: Optional[int] = Field(None, ge=0)
    temperature: Optional[float] = None
    uptime: Optional[int] = Field(None, ge=0)  # in seconds
    load_average: Optional[List[float]] = None
    
    class Config:
        from_attributes = True


class DeviceAlert(BaseModel):
    """Schema for device alerts"""
    device_id: str
    alert_type: str = Field(..., min_length=1, max_length=50)
    severity: str = Field(..., regex=r'^(info|warning|critical)$')
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False
    metadata: Optional[Dict[str, Any]] = None


class DeviceConfigTemplate(BaseModel):
    """Schema for device configuration templates"""
    name: str = Field(..., min_length=1, max_length=100)
    device_type: DeviceType
    description: Optional[str] = None
    config_data: Dict[str, Any]
    variables: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    
    class Config:
        from_attributes = True