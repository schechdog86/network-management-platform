"""
Notification management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.notification import Notification, NotificationType, NotificationSource
from app.core.logging_config import logger

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=List[dict])
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: Optional[NotificationType] = None,
    source: Optional[NotificationSource] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notifications for the current user or system-wide notifications.
    """
    try:
        # Build query
        query = select(Notification).where(
            or_(
                Notification.user_id == current_user.id,
                Notification.user_id.is_(None)  # System-wide notifications
            )
        )
        
        # Apply filters
        if unread_only:
            query = query.where(Notification.read == False)
        
        if notification_type:
            query = query.where(Notification.type == notification_type)
        
        if source:
            query = query.where(Notification.source == source)
        
        # Order by created_at descending (newest first)
        query = query.order_by(Notification.created_at.desc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return [notification.to_dict() for notification in notifications]
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get count of unread notifications.
    """
    try:
        query = select(Notification).where(
            and_(
                or_(
                    Notification.user_id == current_user.id,
                    Notification.user_id.is_(None)
                ),
                Notification.read == False
            )
        )
        
        result = await db.execute(query)
        count = len(result.scalars().all())
        
        return {"unread_count": count}
        
    except Exception as e:
        logger.error(f"Error counting unread notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a notification as read.
    """
    try:
        # Get notification
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                or_(
                    Notification.user_id == current_user.id,
                    Notification.user_id.is_(None)
                )
            )
        )
        
        result = await db.execute(query)
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Update notification
        notification.read = True
        notification.read_at = datetime.utcnow()
        
        await db.commit()
        
        return {"status": "success", "message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark all notifications as read for the current user.
    """
    try:
        # Update all unread notifications
        stmt = (
            update(Notification)
            .where(
                and_(
                    or_(
                        Notification.user_id == current_user.id,
                        Notification.user_id.is_(None)
                    ),
                    Notification.read == False
                )
            )
            .values(read=True, read_at=datetime.utcnow())
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Marked {result.rowcount} notifications as read"
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a notification.
    """
    try:
        # Check if notification exists and belongs to user
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                or_(
                    Notification.user_id == current_user.id,
                    and_(
                        Notification.user_id.is_(None),
                        current_user.is_superuser == True  # Only admins can delete system notifications
                    )
                )
            )
        )
        
        result = await db.execute(query)
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Delete notification
        await db.delete(notification)
        await db.commit()
        
        return {"status": "success", "message": "Notification deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def create_test_notification(
    title: str = "Test Notification",
    message: str = "This is a test notification",
    notification_type: NotificationType = NotificationType.INFO,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a test notification (admin only).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        notification = Notification(
            title=title,
            message=message,
            type=notification_type,
            source=NotificationSource.SYSTEM,
            metadata={"test": True, "created_by": current_user.username},
            created_at=datetime.utcnow()
        )
        
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        return notification.to_dict()
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating test notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))