"""
CI/CD tracking and deployment API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any
from datetime import datetime
from app.services.cicd_tracker import cicd_tracker, DeploymentEnvironment, DeploymentStatus
from app.api.deps import get_current_user
from app.models.user import User
from app.core.logging_config import logger

router = APIRouter(prefix="/cicd", tags=["cicd"])


@router.get("/deployments")
async def get_deployment_status(
    environment: Optional[DeploymentEnvironment] = Query(None, description="Filter by environment"),
    current_user: User = Depends(get_current_user)
):
    """
    Get deployment status and history.
    """
    try:
        return await cicd_tracker.get_deployment_status(environment=environment)
    except Exception as e:
        logger.error(f"Error fetching deployment status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/metrics")
async def get_workflow_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get workflow execution metrics and statistics.
    """
    try:
        return await cicd_tracker.get_workflow_metrics()
    except Exception as e:
        logger.error(f"Error fetching workflow metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deployments/trigger")
async def trigger_deployment(
    environment: DeploymentEnvironment,
    branch: str = "main",
    current_user: User = Depends(get_current_user)
):
    """
    Trigger a deployment to specified environment.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        return await cicd_tracker.trigger_deployment(environment=environment, branch=branch)
    except Exception as e:
        logger.error(f"Error triggering deployment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/start")
async def start_cicd_monitoring(
    current_user: User = Depends(get_current_user)
):
    """
    Start CI/CD monitoring service.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        await cicd_tracker.start_monitoring()
        return {"status": "success", "message": "CI/CD monitoring started"}
    except Exception as e:
        logger.error(f"Error starting CI/CD monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/stop")
async def stop_cicd_monitoring(
    current_user: User = Depends(get_current_user)
):
    """
    Stop CI/CD monitoring service.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        await cicd_tracker.stop_monitoring()
        return {"status": "success", "message": "CI/CD monitoring stopped"}
    except Exception as e:
        logger.error(f"Error stopping CI/CD monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/summary")
async def get_cicd_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive CI/CD status summary including deployments and workflows.
    """
    try:
        deployment_status = await cicd_tracker.get_deployment_status()
        workflow_metrics = await cicd_tracker.get_workflow_metrics()
        
        # Combine data for comprehensive view
        return {
            "deployments": deployment_status,
            "workflows": workflow_metrics,
            "monitoring_active": cicd_tracker._monitoring_task is not None and not cicd_tracker._monitoring_task.done(),
            "last_check": datetime.utcnow().isoformat() if cicd_tracker.workflow_cache else None,
        }
    except Exception as e:
        logger.error(f"Error fetching CI/CD summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))