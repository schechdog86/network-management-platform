"""
Device models for network management
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, INET, MACADDR, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Device(Base):
    """Network device model"""
    __tablename__ = "devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname = Column(String(255), nullable=False, index=True)
    ip_address = Column(INET, nullable=False, unique=True, index=True)
    mac_address = Column(MACADDR, nullable=True, index=True)
    device_type = Column(String(50), nullable=False, index=True)  # server, router, switch, etc.
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    os_info = Column(JSONB, nullable=True)
    hardware_specs = Column(JSONB, nullable=True)
    
    # Status and metadata
    status = Column(String(20), nullable=False, default="unknown", index=True)  # online, offline, unknown
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_scan = Column(DateTime(timezone=True), nullable=True)
    
    # Management information
    snmp_community = Column(String(100), nullable=True)
    snmp_version = Column(String(10), nullable=True)
    ssh_username = Column(String(100), nullable=True)
    ssh_port = Column(Integer, default=22)
    
    # Monitoring configuration
    monitoring_enabled = Column(Boolean, default=True)
    backup_enabled = Column(Boolean, default=False)
    
    # Metadata
    tags = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    metrics = relationship("DeviceMetric", back_populates="device", cascade="all, delete-orphan")
    status_history = relationship("DeviceStatus", back_populates="device", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_device_type_status', 'device_type', 'status'),
        Index('idx_device_last_seen', 'last_seen'),
        Index('idx_device_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Device(hostname='{self.hostname}', ip='{self.ip_address}', type='{self.device_type}')>"


class DeviceMetric(Base):
    """Time-series metrics for devices"""
    __tablename__ = "device_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Metric information
    metric_type = Column(String(50), nullable=False, index=True)  # cpu, memory, disk, network, etc.
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)
    
    # Additional metadata
    tags = Column(JSONB, nullable=True)
    extra_data = Column(JSONB, nullable=True)
    
    # Relationships
    device = relationship("Device", back_populates="metrics")
    
    # Indexes for TimescaleDB optimization
    __table_args__ = (
        Index('idx_device_metrics_time_device', 'timestamp', 'device_id'),
        Index('idx_device_metrics_type_time', 'metric_type', 'timestamp'),
        Index('idx_device_metrics_device_type', 'device_id', 'metric_type'),
    )
    
    def __repr__(self):
        return f"<DeviceMetric(device_id='{self.device_id}', type='{self.metric_type}', value='{self.value}')>"


class DeviceStatus(Base):
    """Device status change history"""
    __tablename__ = "device_status_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Status information
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    reason = Column(String(255), nullable=True)
    
    # Detection information
    detected_by = Column(String(100), nullable=True)  # scanner, manual, alert, etc.
    detection_method = Column(String(100), nullable=True)  # ping, snmp, ssh, etc.
    
    # Additional context
    extra_data = Column(JSONB, nullable=True)
    
    # Relationships
    device = relationship("Device", back_populates="status_history")
    
    # Indexes
    __table_args__ = (
        Index('idx_device_status_time_device', 'timestamp', 'device_id'),
        Index('idx_device_status_new_status', 'new_status', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<DeviceStatus(device_id='{self.device_id}', {self.old_status}->{self.new_status})>"