"""
Snap Update Management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import asyncio

from app.database import get_db
from app.auth import get_current_user
from app.models import User
from app.services.update_manager import UpdateManagerService
from app.services.websocket_manager import WebSocketManager
from app.schemas.updates import (
    UpdateStatus,
    UpdateRequest,
    UpdateResponse,
    UpdatePolicy,
    UpdateSchedule,
    FleetUpdateRequest,
    FleetUpdateResponse,
    NodeUpdateStatus,
    UpdateHistoryResponse,
)

router = APIRouter()
update_service = UpdateManagerService()
ws_manager = WebSocketManager()


@router.get("/status/{node_id}", response_model=NodeUpdateStatus)
async def get_node_update_status(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get update status for a specific node"""
    try:
        status = await update_service.get_node_status(node_id)
        return NodeUpdateStatus(**status)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get node update status: {str(e)}"
        )


@router.get("/status", response_model=List[NodeUpdateStatus])
async def get_all_nodes_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get update status for all nodes"""
    try:
        statuses = await update_service.get_all_nodes_status()
        return [NodeUpdateStatus(**status) for status in statuses]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get nodes update status: {str(e)}"
        )


@router.post("/check/{node_id}")
async def check_for_updates(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger update check for a specific node"""
    try:
        result = await update_service.trigger_update_check(node_id)
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "update_check_triggered",
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": f"Update check triggered for node {node_id}", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger update check: {str(e)}"
        )


@router.post("/install/{node_id}", response_model=UpdateResponse)
async def install_updates(
    node_id: str,
    request: UpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Install updates on a specific node"""
    try:
        # Validate the request
        if not request.snap_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No snaps specified for update"
            )
            
        # Trigger the update
        result = await update_service.install_updates(
            node_id=node_id,
            snap_names=request.snap_names,
            force=request.force,
            channel=request.channel
        )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "update_installation_started",
            "node_id": node_id,
            "snap_names": request.snap_names,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return UpdateResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install updates: {str(e)}"
        )


@router.post("/rollback/{node_id}")
async def rollback_snap(
    node_id: str,
    snap_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rollback a snap to previous revision"""
    try:
        result = await update_service.rollback_snap(node_id, snap_name)
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "snap_rollback_triggered",
            "node_id": node_id,
            "snap_name": snap_name,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": f"Rollback triggered for {snap_name} on node {node_id}", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback snap: {str(e)}"
        )


@router.post("/fleet", response_model=FleetUpdateResponse)
async def update_fleet(
    request: FleetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform fleet-wide update with staged rollout"""
    try:
        # Validate the request
        if not request.node_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No nodes specified for fleet update"
            )
            
        if not request.snap_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No snaps specified for update"
            )
            
        # Start fleet update
        result = await update_service.start_fleet_update(
            node_ids=request.node_ids,
            snap_names=request.snap_names,
            rollout_strategy=request.rollout_strategy,
            canary_percentage=request.canary_percentage,
            batch_size=request.batch_size,
            delay_between_batches=request.delay_between_batches
        )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "fleet_update_started",
            "update_id": result["update_id"],
            "node_count": len(request.node_ids),
            "snap_names": request.snap_names,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return FleetUpdateResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start fleet update: {str(e)}"
        )


@router.get("/fleet/{update_id}")
async def get_fleet_update_status(
    update_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get status of a fleet update"""
    try:
        status = await update_service.get_fleet_update_status(update_id)
        return status
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fleet update status: {str(e)}"
        )


@router.delete("/fleet/{update_id}")
async def cancel_fleet_update(
    update_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a running fleet update"""
    try:
        result = await update_service.cancel_fleet_update(update_id)
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "fleet_update_cancelled",
            "update_id": update_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": f"Fleet update {update_id} cancelled", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel fleet update: {str(e)}"
        )


@router.get("/policy/{node_id}", response_model=UpdatePolicy)
async def get_update_policy(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get update policy for a node"""
    try:
        policy = await update_service.get_update_policy(node_id)
        return UpdatePolicy(**policy)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get update policy: {str(e)}"
        )


@router.put("/policy/{node_id}")
async def update_policy(
    node_id: str,
    policy: UpdatePolicy,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update policy for a node"""
    try:
        result = await update_service.update_policy(node_id, policy.dict())
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "update_policy_changed",
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": f"Update policy updated for node {node_id}", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update policy: {str(e)}"
        )


@router.get("/schedule/{node_id}", response_model=UpdateSchedule)
async def get_update_schedule(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get update schedule for a node"""
    try:
        schedule = await update_service.get_update_schedule(node_id)
        return UpdateSchedule(**schedule)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get update schedule: {str(e)}"
        )


@router.put("/schedule/{node_id}")
async def update_schedule(
    node_id: str,
    schedule: UpdateSchedule,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update schedule for a node"""
    try:
        result = await update_service.update_schedule(node_id, schedule.dict())
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "update_schedule_changed",
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": f"Update schedule updated for node {node_id}", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule: {str(e)}"
        )


@router.get("/history/{node_id}", response_model=List[UpdateHistoryResponse])
async def get_update_history(
    node_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get update history for a node"""
    try:
        history = await update_service.get_update_history(node_id, limit, offset)
        return [UpdateHistoryResponse(**item) for item in history]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get update history: {str(e)}"
        )


@router.post("/status")
async def report_update_status(
    status_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Receive update status reports from nodes"""
    try:
        # Process the status update
        result = await update_service.process_status_report(status_data)
        
        # Broadcast to WebSocket clients
        await ws_manager.broadcast(json.dumps({
            "type": "update_status_report",
            "data": status_data,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": "Status report received", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process status report: {str(e)}"
        )


@router.post("/emergency-stop")
async def emergency_stop_all_updates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Emergency stop all running updates"""
    try:
        result = await update_service.emergency_stop_all_updates()
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "emergency_stop_triggered",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": "Emergency stop triggered for all updates", "result": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger emergency stop: {str(e)}"
        )