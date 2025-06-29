"""
System-related database models
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class SystemLog(Base):
    """System logs and audit trail"""
    __tablename__ = "system_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Log details
    level = Column(String(20), nullable=False, index=True)  # debug, info, warning, error, critical
    logger_name = Column(String(255), nullable=False, index=True)
    module = Column(String(255), nullable=True)
    function = Column(String(255), nullable=True)
    
    # Message
    message = Column(Text, nullable=False)
    extra_data = Column(JSONB, nullable=True)
    
    # Context
    user_id = Column(String(255), nullable=True)
    request_id = Column(String(255), nullable=True)
    trace_id = Column(String(255), nullable=True)
    
    # Error information
    exception_type = Column(String(255), nullable=True)
    exception_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_system_log_time_level', 'timestamp', 'level'),
        Index('idx_system_log_logger', 'logger_name', 'timestamp'),
        Index('idx_system_log_user', 'user_id', 'timestamp'),
    )


class SystemEvent(Base):
    """System-wide events and notifications"""
    __tablename__ = "system_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Event information
    event_type = Column(String(50), nullable=False, index=True)  # startup, shutdown, config_change, etc.
    event_category = Column(String(50), nullable=False)  # system, security, performance, etc.
    severity = Column(String(20), nullable=False)  # info, warning, error, critical
    
    # Event details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_data = Column(JSONB, nullable=True)
    
    # Source information
    source = Column(String(255), nullable=False)  # Component or service that generated the event
    hostname = Column(String(255), nullable=True)
    
    # Impact assessment
    affected_components = Column(JSONB, nullable=True)  # List of affected components
    impact_level = Column(String(20), nullable=True)  # high, medium, low
    
    # Response
    auto_resolved = Column(DateTime(timezone=True), nullable=True)
    acknowledged = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(255), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_system_event_time_type', 'timestamp', 'event_type'),
        Index('idx_system_event_severity', 'severity', 'timestamp'),
        Index('idx_system_event_source', 'source', 'timestamp'),
    )