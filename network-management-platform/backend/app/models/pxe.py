"""
Database models for PXE boot management
"""

from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from enum import Enum

from app.core.database import Base


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OSType(str, Enum):
    UBUNTU_2204 = "ubuntu2204"
    UBUNTU_2404 = "ubuntu2404"
    DEBIAN_12 = "debian12"
    CENTOS_9 = "centos9"
    RHEL_9 = "rhel9"
    CUSTOM = "custom"


class PXEDeploymentJob(Base):
    """PXE deployment job tracking"""
    __tablename__ = "pxe_deployment_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Target information
    target_mac = Column(String(17), nullable=False)  # MAC address format: XX:XX:XX:XX:XX:XX
    target_ip = Column(String(45), nullable=True)    # IPv4 or IPv6
    
    # Deployment configuration
    os_type = Column(String(50), nullable=False)  # OSType enum
    hostname = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    
    # Configuration details
    config = Column(JSON, nullable=False)  # Full deployment configuration
    
    # Status tracking
    status = Column(String(50), nullable=False, default=DeploymentStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # Progress tracking
    progress_percent = Column(Integer, default=0)
    current_stage = Column(String(255), nullable=True)
    
    # Timing
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)


class DHCPReservation(Base):
    """DHCP MAC to IP reservations"""
    __tablename__ = "dhcp_reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mac_address = Column(String(17), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    
    # Optional reservation details
    hostname = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # Status
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Metadata
    created_by = Column(String(255), nullable=True)


class DHCPLease(Base):
    """Active DHCP leases"""
    __tablename__ = "dhcp_leases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mac_address = Column(String(17), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    
    # Lease details
    lease_time = Column(Integer, nullable=False)  # Lease time in seconds
    client_hostname = Column(String(255), nullable=True)
    
    # Timing
    granted_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    # Status
    active = Column(Boolean, default=True)
    
    # Metadata
    vendor_class = Column(String(255), nullable=True)
    user_class = Column(String(255), nullable=True)


class PXEServerConfig(Base):
    """PXE server configuration"""
    __tablename__ = "pxe_server_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    
    # Network configuration
    interface = Column(String(50), nullable=False)
    subnet = Column(String(50), nullable=False)  # CIDR notation
    
    # Server addresses
    tftp_server = Column(String(45), nullable=False)
    http_server = Column(String(255), nullable=False)
    
    # Paths
    tftp_root = Column(String(1024), nullable=False)
    http_root = Column(String(1024), nullable=False)
    
    # Ports
    tftp_port = Column(Integer, default=69)
    http_port = Column(Integer, default=8080)
    
    # Boot mode
    boot_mode = Column(String(10), default="both")  # bios, uefi, both
    
    # Status
    active = Column(Boolean, default=False)
    last_started = Column(DateTime, nullable=True)
    last_stopped = Column(DateTime, nullable=True)
    
    # Configuration
    config = Column(JSON, nullable=True)  # Additional configuration options
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class OSImage(Base):
    """Available OS images for deployment"""
    __tablename__ = "os_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    
    # OS details
    os_type = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)
    architecture = Column(String(20), nullable=False)  # amd64, arm64, etc.
    
    # Installation method
    install_method = Column(String(50), nullable=False)  # preseed, kickstart, autoinstall
    
    # File paths
    kernel_path = Column(String(1024), nullable=True)
    initrd_path = Column(String(1024), nullable=True)
    iso_path = Column(String(1024), nullable=True)
    
    # Status
    available = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)
    
    # Metadata
    size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(128), nullable=True)
    checksum_type = Column(String(20), nullable=True)  # sha256, md5, etc.
    
    # Configuration template
    default_config = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())