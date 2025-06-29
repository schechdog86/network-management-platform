"""
Notification model for system notifications.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum
from datetime import datetime
from app.db.base_class import Base


class NotificationType(str, Enum):
    """Notification type enumeration"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationSource(str, Enum):
    """Notification source enumeration"""
    SYSTEM = "system"
    GITHUB = "github"
    DEVICE = "device"
    NETWORK = "network"
    SECURITY = "security"
    BACKUP = "backup"
    AI = "ai"
    USER = "user"


class Notification(Base):
    """Notification model"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(SQLEnum(NotificationType), nullable=False, default=NotificationType.INFO)
    source = Column(String(50), nullable=False, default=NotificationSource.SYSTEM)
    read = Column(Boolean, default=False, nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(Integer, nullable=True)  # Null for system-wide notifications
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "source": self.source,
            "read": self.read,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "user_id": self.user_id,
        }