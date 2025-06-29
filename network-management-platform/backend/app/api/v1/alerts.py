"""
System alerts API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any
from app.services.system_alerts import system_alert_service, AlertType, AlertSeverity
from app.api.deps import get_current_user
from app.models.user import User
from app.core.logging_config import logger

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/monitoring/start")
async def start_alert_monitoring(
    current_user: User = Depends(get_current_user)
):
    """
    Start system alert monitoring service.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        await system_alert_service.start_monitoring()
        return {"status": "success", "message": "System alert monitoring started"}
    except Exception as e:
        logger.error(f"Error starting alert monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/stop")
async def stop_alert_monitoring(
    current_user: User = Depends(get_current_user)
):
    """
    Stop system alert monitoring service.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        await system_alert_service.stop_monitoring()
        return {"status": "success", "message": "System alert monitoring stopped"}
    except Exception as e:
        logger.error(f"Error stopping alert monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thresholds")
async def get_alert_thresholds(
    current_user: User = Depends(get_current_user)
):
    """
    Get current alert thresholds.
    """
    return {
        "thresholds": system_alert_service.alert_thresholds,
        "cooldown_seconds": system_alert_service.alert_cooldown,
        "monitoring_interval_seconds": system_alert_service.monitoring_interval,
    }


@router.put("/thresholds")
async def update_alert_thresholds(
    thresholds: Dict[str, float],
    current_user: User = Depends(get_current_user)
):
    """
    Update alert thresholds.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        # Validate thresholds
        valid_keys = set(system_alert_service.alert_thresholds.keys())
        provided_keys = set(thresholds.keys())
        
        if not provided_keys.issubset(valid_keys):
            invalid_keys = provided_keys - valid_keys
            raise HTTPException(
                status_code=400,
                detail=f"Invalid threshold keys: {invalid_keys}"
            )
        
        # Update thresholds
        system_alert_service.alert_thresholds.update(thresholds)
        
        return {
            "status": "success",
            "message": "Alert thresholds updated",
            "thresholds": system_alert_service.alert_thresholds
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def create_test_alert(
    alert_type: AlertType,
    severity: AlertSeverity,
    current_user: User = Depends(get_current_user)
):
    """
    Create a test alert for testing the alert system.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        result = await system_alert_service.test_alert(
            alert_type=alert_type,
            severity=severity
        )
        return result
    except Exception as e:
        logger.error(f"Error creating test alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_alert_monitoring_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current status of the alert monitoring system.
    """
    monitoring_active = (
        system_alert_service._monitoring_task is not None 
        and not system_alert_service._monitoring_task.done()
    )
    
    return {
        "monitoring_active": monitoring_active,
        "active_alerts": len(system_alert_service.active_alerts),
        "alert_types": [alert_type.value for alert_type in AlertType],
        "severity_levels": [severity.value for severity in AlertSeverity],
        "thresholds": system_alert_service.alert_thresholds,
    }