"""
Network-related database models
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Text, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class NetworkScan(Base):
    """Network scan job tracking"""
    __tablename__ = "network_scans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    scan_type = Column(String(50), nullable=False)  # discovery, port_scan, vulnerability, etc.
    status = Column(String(20), nullable=False, default="pending")
    
    # Target configuration
    target_network = Column(INET, nullable=False, index=True)
    port_range = Column(String(100), nullable=True)
    scan_options = Column(JSONB, nullable=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Results
    hosts_discovered = Column(Integer, default=0)
    ports_open = Column(Integer, default=0)
    vulnerabilities_found = Column(Integer, default=0)
    
    # Scan data
    result_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    events = relationship("NetworkEvent", back_populates="scan")
    
    # Indexes
    __table_args__ = (
        Index('idx_network_scan_status', 'status'),
        Index('idx_network_scan_created', 'created_at'),
    )


class NetworkEvent(Base):
    """Network events and alerts"""
    __tablename__ = "network_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # alert, discovery, status_change, etc.
    severity = Column(String(20), nullable=False)  # critical, high, medium, low, info
    
    # Event details
    source_ip = Column(INET, nullable=True, index=True)
    destination_ip = Column(INET, nullable=True, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("network_scans.id"), nullable=True)
    
    # Event information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_data = Column(JSONB, nullable=True)
    
    # Status
    acknowledged = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(255), nullable=True)
    resolved = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(255), nullable=True)
    
    # Relationships
    device = relationship("Device", foreign_keys=[device_id])
    scan = relationship("NetworkScan", back_populates="events")
    
    # Indexes
    __table_args__ = (
        Index('idx_network_event_time_type', 'timestamp', 'event_type'),
        Index('idx_network_event_severity', 'severity', 'timestamp'),
        Index('idx_network_event_device', 'device_id', 'timestamp'),
    )


class NetworkTopology(Base):
    """Network topology mapping"""
    __tablename__ = "network_topology"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Topology data
    topology_type = Column(String(50), nullable=False)  # physical, logical, vlan, etc.
    topology_data = Column(JSONB, nullable=False)  # Graph data structure
    
    # Network information
    network_segments = Column(JSONB, nullable=True)  # List of network segments
    device_count = Column(Integer, default=0)
    connection_count = Column(Integer, default=0)
    
    # Visualization data
    layout_data = Column(JSONB, nullable=True)  # UI layout information
    visualization_config = Column(JSONB, nullable=True)
    
    # Status
    active = Column(String(20), default="active")
    last_scan = Column(DateTime(timezone=True), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_topology_type', 'topology_type'),
        Index('idx_topology_updated', 'updated_at'),
    )