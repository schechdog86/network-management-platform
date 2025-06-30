"""
Snap Distribution API Endpoints
Provides REST API for enterprise snap distribution and rollout management
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.user import User
from app.services.snap_distribution_service import (
    snap_distribution_service,
    SnapDistribution,
    SnapChannel,
    RolloutPolicy,
    RolloutStrategy,
    ChannelRisk
)

router = APIRouter()


# Pydantic models for API

class SnapChannelRequest(BaseModel):
    """Snap channel configuration"""
    track: str = "latest"
    risk: str = "stable"
    branch: Optional[str] = None


class RolloutPolicyRequest(BaseModel):
    """Rollout policy configuration"""
    strategy: str = "progressive"
    phases: List[int] = [10, 30, 70, 100]
    phase_duration_hours: int = 24
    rollback_threshold_percent: float = 5.0
    health_check_enabled: bool = True
    approval_required: bool = False
    target_groups: Optional[List[str]] = None
    exclude_groups: Optional[List[str]] = None


class SnapDistributionRequest(BaseModel):
    """Request to create snap distribution"""
    snap_name: str = Field(..., description="Name of the snap to distribute")
    source_channel: SnapChannelRequest = Field(..., description="Source channel configuration")
    target_channel: SnapChannelRequest = Field(..., description="Target channel configuration")
    target_devices: List[str] = Field(..., description="List of target device IDs")
    rollout_policy: RolloutPolicyRequest = Field(..., description="Rollout policy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class StoreProxyRegistrationRequest(BaseModel):
    """Request to register snap store proxy"""
    proxy_id: str = Field(..., description="Unique identifier for the proxy")
    endpoint: str = Field(..., description="Proxy endpoint URL")
    auth_token: Optional[str] = Field(None, description="Authentication token")


class DistributionResponse(BaseModel):
    """Response for distribution operations"""
    distribution_id: str
    message: str
    status: str


class DistributionStatusResponse(BaseModel):
    """Response for distribution status"""
    distribution_id: str
    snap_name: str
    current_phase: int
    total_phases: int
    devices_targeted: int
    devices_updated: int
    devices_failed: int
    progress_percent: float
    status: str
    phase_start_time: str
    next_phase_time: Optional[str]
    errors: List[str]
    health_metrics: Dict[str, Any]


@router.post("/store-proxy/register", response_model=Dict[str, str])
async def register_store_proxy(
    request: StoreProxyRegistrationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Register a snap store proxy for distribution caching and control
    """
    try:
        await snap_distribution_service.register_store_proxy(
            request.proxy_id,
            request.endpoint,
            request.auth_token
        )
        
        return {
            "message": f"Successfully registered store proxy: {request.proxy_id}",
            "proxy_id": request.proxy_id,
            "status": "registered"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to register store proxy: {str(e)}"
        )


@router.get("/store-proxy/list")
async def list_store_proxies(
    current_user: User = Depends(get_current_user)
):
    """
    List registered snap store proxies
    """
    try:
        # Get proxy information from cache
        proxies = []
        for proxy_id in snap_distribution_service.store_proxy_clients.keys():
            cache_key = f"snap_proxy:{proxy_id}"
            proxy_info = await cache_manager.get(cache_key)
            if proxy_info:
                import json
                proxies.append({
                    "proxy_id": proxy_id,
                    **json.loads(proxy_info)
                })
                
        return {"proxies": proxies}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list store proxies: {str(e)}"
        )


@router.post("/distributions", response_model=DistributionResponse)
async def create_distribution(
    request: SnapDistributionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new snap distribution with rollout policy
    """
    try:
        # Convert request to internal models
        source_channel = SnapChannel(
            track=request.source_channel.track,
            risk=ChannelRisk(request.source_channel.risk),
            branch=request.source_channel.branch
        )
        
        target_channel = SnapChannel(
            track=request.target_channel.track,
            risk=ChannelRisk(request.target_channel.risk),
            branch=request.target_channel.branch
        )
        
        rollout_policy = RolloutPolicy(
            strategy=RolloutStrategy(request.rollout_policy.strategy),
            phases=request.rollout_policy.phases,
            phase_duration_hours=request.rollout_policy.phase_duration_hours,
            rollback_threshold_percent=request.rollout_policy.rollback_threshold_percent,
            health_check_enabled=request.rollout_policy.health_check_enabled,
            approval_required=request.rollout_policy.approval_required,
            target_groups=request.rollout_policy.target_groups,
            exclude_groups=request.rollout_policy.exclude_groups
        )
        
        distribution = SnapDistribution(
            snap_name=request.snap_name,
            source_channel=source_channel,
            target_channel=target_channel,
            target_devices=request.target_devices,
            rollout_policy=rollout_policy,
            metadata=request.metadata,
            created_by=current_user.username
        )
        
        # Create the distribution
        distribution_id = await snap_distribution_service.create_distribution(distribution)
        
        return DistributionResponse(
            distribution_id=distribution_id,
            message=f"Successfully created distribution for {request.snap_name}",
            status="created"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create distribution: {str(e)}"
        )


@router.get("/distributions", response_model=List[DistributionStatusResponse])
async def list_distributions(
    status: Optional[str] = Query(None, description="Filter by status"),
    snap_name: Optional[str] = Query(None, description="Filter by snap name"),
    current_user: User = Depends(get_current_user)
):
    """
    List active snap distributions
    """
    try:
        distributions = await snap_distribution_service.list_active_distributions()
        
        # Apply filters
        if status:
            distributions = [d for d in distributions if d['status'] == status]
            
        if snap_name:
            distributions = [d for d in distributions if d['snap_name'] == snap_name]
            
        return [DistributionStatusResponse(**dist) for dist in distributions]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list distributions: {str(e)}"
        )


@router.get("/distributions/{distribution_id}", response_model=DistributionStatusResponse)
async def get_distribution_status(
    distribution_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get status of a specific distribution
    """
    try:
        status = await snap_distribution_service.get_distribution_status(distribution_id)
        return DistributionStatusResponse(**status)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get distribution status: {str(e)}"
        )


@router.post("/distributions/{distribution_id}/pause", response_model=Dict[str, str])
async def pause_distribution(
    distribution_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Pause an active distribution
    """
    try:
        await snap_distribution_service.pause_distribution(distribution_id)
        
        return {
            "message": f"Successfully paused distribution {distribution_id}",
            "distribution_id": distribution_id,
            "status": "paused"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause distribution: {str(e)}"
        )


@router.post("/distributions/{distribution_id}/resume", response_model=Dict[str, str])
async def resume_distribution(
    distribution_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Resume a paused distribution
    """
    try:
        await snap_distribution_service.resume_distribution(distribution_id)
        
        return {
            "message": f"Successfully resumed distribution {distribution_id}",
            "distribution_id": distribution_id,
            "status": "resumed"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume distribution: {str(e)}"
        )


@router.post("/distributions/{distribution_id}/rollback", response_model=Dict[str, str])
async def rollback_distribution(
    distribution_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Rollback a distribution to previous version
    """
    try:
        await snap_distribution_service.rollback_distribution(distribution_id)
        
        return {
            "message": f"Successfully initiated rollback for distribution {distribution_id}",
            "distribution_id": distribution_id,
            "status": "rolling_back"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rollback distribution: {str(e)}"
        )


@router.get("/channels/available")
async def get_available_channels(
    snap_name: Optional[str] = Query(None, description="Snap name to get channels for"),
    current_user: User = Depends(get_current_user)
):
    """
    Get available channels for snap distribution
    """
    try:
        # Standard snap channels
        channels = {
            "tracks": ["latest"],
            "risks": ["stable", "candidate", "beta", "edge"],
            "branches": []
        }
        
        # If snap_name provided, could query actual channels from snap store
        # For now, return standard channels
        
        return {
            "snap_name": snap_name,
            "channels": channels
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available channels: {str(e)}"
        )


@router.get("/rollout-strategies")
async def get_rollout_strategies(
    current_user: User = Depends(get_current_user)
):
    """
    Get available rollout strategies and their configurations
    """
    try:
        strategies = {
            "immediate": {
                "name": "Immediate",
                "description": "Deploy to all devices immediately",
                "supports_phases": False,
                "supports_approval": False
            },
            "progressive": {
                "name": "Progressive",
                "description": "Deploy in phases with configurable percentages",
                "supports_phases": True,
                "supports_approval": True,
                "default_phases": [10, 30, 70, 100]
            },
            "canary": {
                "name": "Canary",
                "description": "Deploy to small subset first, then full rollout",
                "supports_phases": True,
                "supports_approval": True,
                "default_phases": [5, 100]
            },
            "scheduled": {
                "name": "Scheduled",
                "description": "Deploy at specific scheduled times",
                "supports_phases": True,
                "supports_approval": True
            }
        }
        
        return {"strategies": strategies}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rollout strategies: {str(e)}"
        )


@router.get("/distributions/{distribution_id}/logs")
async def get_distribution_logs(
    distribution_id: str,
    limit: int = Query(100, description="Maximum number of log entries"),
    current_user: User = Depends(get_current_user)
):
    """
    Get logs for a specific distribution
    """
    try:
        # Get distribution status to check if it exists
        status = await snap_distribution_service.get_distribution_status(distribution_id)
        
        # For now, return errors from the status
        # In a full implementation, this would query detailed logs
        logs = []
        
        for i, error in enumerate(status['errors'][-limit:]):
            logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "level": "error",
                "message": error,
                "distribution_id": distribution_id
            })
            
        return {
            "distribution_id": distribution_id,
            "logs": logs,
            "total_logs": len(logs)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get distribution logs: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for snap distribution service
    """
    try:
        service_status = "running" if snap_distribution_service.running else "stopped"
        active_distributions = len(snap_distribution_service.active_distributions)
        active_proxies = len(snap_distribution_service.store_proxy_clients)
        
        return {
            "service_status": service_status,
            "active_distributions": active_distributions,
            "active_proxies": active_proxies,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )