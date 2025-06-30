"""
Ray worker management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.core.logging_config import logger
from app.services.websocket_service import websocket_manager
import json

router = APIRouter(prefix="/ray/worker", tags=["ray-worker"])


# In-memory storage for worker status (should be in database for production)
worker_registry: Dict[str, Dict[str, Any]] = {}
task_history: List[Dict[str, Any]] = []
actor_registry: Dict[str, Dict[str, Any]] = {}


@router.post("/status")
async def report_worker_status(
    status_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Receive status updates from Ray workers.
    Called by workers to report their current status.
    """
    try:
        node_id = status_data.get("node_id")
        worker_id = status_data.get("worker_id")
        status = status_data.get("status")
        
        if not node_id:
            raise HTTPException(status_code=400, detail="node_id is required")
            
        # Update worker registry
        worker_key = f"{node_id}:{worker_id}" if worker_id else node_id
        worker_registry[worker_key] = {
            **status_data,
            "last_update": datetime.utcnow().isoformat()
        }
        
        # Broadcast status update via WebSocket
        await websocket_manager.broadcast(json.dumps({
            "type": "ray_worker_status",
            "data": status_data
        }))
        
        logger.info(f"Worker status updated: {worker_key} - {status}")
        
        return {"status": "success", "message": "Status updated"}
        
    except Exception as e:
        logger.error(f"Error updating worker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_workers(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user)
):
    """
    List all registered Ray workers.
    """
    workers = list(worker_registry.values())
    
    # Filter by status if provided
    if status:
        workers = [w for w in workers if w.get("status") == status]
        
    # Sort by last update time
    workers.sort(key=lambda x: x.get("last_update", ""), reverse=True)
    
    return {
        "total": len(workers),
        "workers": workers
    }


@router.get("/{node_id}")
async def get_worker_details(
    node_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific worker.
    """
    # Find worker by node_id
    worker_data = None
    for key, data in worker_registry.items():
        if data.get("node_id") == node_id:
            worker_data = data
            break
            
    if not worker_data:
        raise HTTPException(status_code=404, detail="Worker not found")
        
    # Get task history for this worker
    worker_tasks = [
        t for t in task_history 
        if t.get("node_id") == node_id
    ][-20:]  # Last 20 tasks
    
    # Get actors on this worker
    worker_actors = [
        a for a in actor_registry.values()
        if a.get("node_id") == node_id
    ]
    
    return {
        "worker": worker_data,
        "recent_tasks": worker_tasks,
        "actors": worker_actors
    }


@router.post("/task/complete")
async def report_task_completion(
    task_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Receive task completion reports from Ray workers.
    """
    try:
        # Add to task history
        task_history.append({
            **task_data,
            "reported_at": datetime.utcnow().isoformat()
        })
        
        # Keep only last 1000 tasks
        if len(task_history) > 1000:
            task_history[:] = task_history[-1000:]
            
        # Broadcast task completion
        await websocket_manager.broadcast(json.dumps({
            "type": "ray_task_complete",
            "data": task_data
        }))
        
        return {"status": "success", "message": "Task completion recorded"}
        
    except Exception as e:
        logger.error(f"Error recording task completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actor/register")
async def register_actor(
    actor_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a named Ray actor.
    """
    try:
        actor_name = actor_data.get("actor_name")
        if not actor_name:
            raise HTTPException(status_code=400, detail="actor_name is required")
            
        # Update actor registry
        actor_registry[actor_name] = {
            **actor_data,
            "registered_at": datetime.utcnow().isoformat()
        }
        
        # Broadcast actor registration
        await websocket_manager.broadcast(json.dumps({
            "type": "ray_actor_registered",
            "data": actor_data
        }))
        
        return {"status": "success", "message": "Actor registered"}
        
    except Exception as e:
        logger.error(f"Error registering actor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actors/list")
async def list_actors(
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    current_user: User = Depends(get_current_user)
):
    """
    List all registered Ray actors.
    """
    actors = list(actor_registry.values())
    
    # Filter by node_id if provided
    if node_id:
        actors = [a for a in actors if a.get("node_id") == node_id]
        
    return {
        "total": len(actors),
        "actors": actors
    }


@router.get("/stats/summary")
async def get_worker_stats_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Get summary statistics for all Ray workers.
    """
    # Count workers by status
    status_counts = {}
    total_resources = {
        "cpus": 0,
        "gpus": 0,
        "memory": 0
    }
    
    for worker in worker_registry.values():
        status = worker.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Sum resources
        resources = worker.get("resources", {}).get("configured", {})
        if resources:
            total_resources["cpus"] += resources.get("cpus", 0) or 0
            total_resources["gpus"] += resources.get("gpus", 0) or 0
            total_resources["memory"] += resources.get("memory", 0) or 0
            
    # Task statistics
    task_stats = {
        "total": len(task_history),
        "success": len([t for t in task_history if t.get("status") == "success"]),
        "failed": len([t for t in task_history if t.get("status") == "failed"]),
        "timeout": len([t for t in task_history if t.get("status") == "timeout"])
    }
    
    # Calculate average task duration
    durations = [t.get("duration_seconds", 0) for t in task_history if t.get("duration_seconds")]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return {
        "workers": {
            "total": len(worker_registry),
            "by_status": status_counts,
            "resources": total_resources
        },
        "tasks": {
            **task_stats,
            "average_duration_seconds": round(avg_duration, 2)
        },
        "actors": {
            "total": len(actor_registry),
            "by_node": {}  # Could group by node if needed
        }
    }


@router.post("/command/{node_id}")
async def send_worker_command(
    node_id: str,
    command: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    Send a command to a specific worker.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    # Find worker
    worker_data = None
    for key, data in worker_registry.items():
        if data.get("node_id") == node_id:
            worker_data = data
            break
            
    if not worker_data:
        raise HTTPException(status_code=404, detail="Worker not found")
        
    # Broadcast command via WebSocket
    await websocket_manager.broadcast(json.dumps({
        "type": "ray_worker_command",
        "node_id": node_id,
        "command": command
    }))
    
    return {
        "status": "success",
        "message": f"Command sent to worker {node_id}",
        "command": command
    }


@router.delete("/{node_id}")
async def remove_worker(
    node_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Remove a worker from the registry.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    # Remove worker
    removed = False
    keys_to_remove = []
    
    for key, data in worker_registry.items():
        if data.get("node_id") == node_id:
            keys_to_remove.append(key)
            removed = True
            
    for key in keys_to_remove:
        del worker_registry[key]
        
    if not removed:
        raise HTTPException(status_code=404, detail="Worker not found")
        
    # Also remove associated actors
    actor_keys_to_remove = [
        name for name, data in actor_registry.items()
        if data.get("node_id") == node_id
    ]
    
    for key in actor_keys_to_remove:
        del actor_registry[key]
        
    return {
        "status": "success",
        "message": f"Worker {node_id} removed",
        "actors_removed": len(actor_keys_to_remove)
    }