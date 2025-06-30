"""
Snapd Management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from app.database import get_db
from app.auth import get_current_user
from app.models import User
from app.services.snapd_service import snapd_service, SnapInfo, SnapChange
from app.services.websocket_manager import WebSocketManager
from app.schemas.snapd import (
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    SnapInstallRequest,
    SnapInstallResponse,
    SnapRefreshRequest,
    SnapRefreshResponse,
    SnapRemoveRequest,
    SnapRemoveResponse,
    SnapInfoResponse,
    SnapChangeResponse,
    SnapListResponse,
    DeviceSystemInfoResponse,
    InterfaceConnectionRequest,
    InterfaceConnectionResponse,
    BulkSnapOperationRequest,
    BulkSnapOperationResponse,
)

router = APIRouter()
ws_manager = WebSocketManager()


@router.post("/devices/{device_id}/register", response_model=DeviceRegistrationResponse)
async def register_device_for_snapd(
    device_id: str,
    request: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a device for snapd management"""
    try:
        system_info = await snapd_service.register_device(
            device_id=device_id,
            endpoint=request.endpoint,
            auth_token=request.auth_token,
            db=db
        )
        
        return DeviceRegistrationResponse(
            device_id=device_id,
            endpoint=request.endpoint,
            system_info=system_info,
            registered_at=datetime.utcnow(),
            status="registered"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device for snapd management: {str(e)}"
        )


@router.delete("/devices/{device_id}/register")
async def unregister_device_from_snapd(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unregister a device from snapd management"""
    try:
        await snapd_service.unregister_device(device_id=device_id, db=db)
        
        return {"message": f"Device {device_id} unregistered from snapd management"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister device from snapd management: {str(e)}"
        )


@router.get("/devices/{device_id}/system-info", response_model=DeviceSystemInfoResponse)
async def get_device_system_info(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get system information from a device via snapd API"""
    try:
        connection = await snapd_service.get_connection(device_id)
        system_info = await connection.get_system_info()
        
        return DeviceSystemInfoResponse(
            device_id=device_id,
            system_info=system_info,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system info: {str(e)}"
        )


@router.get("/devices/{device_id}/snaps", response_model=SnapListResponse)
async def list_device_snaps(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List snaps installed on a device"""
    try:
        snaps = await snapd_service.list_device_snaps(device_id)
        
        snap_data = []
        for snap in snaps:
            snap_data.append({
                'name': snap.name,
                'version': snap.version,
                'revision': snap.revision,
                'status': snap.status,
                'channel': snap.channel,
                'installed_size': snap.installed_size,
                'install_date': snap.install_date,
                'summary': snap.summary,
                'description': snap.description,
                'developer': snap.developer,
                'tracking_channel': snap.tracking_channel,
                'refresh_date': snap.refresh_date
            })
            
        return SnapListResponse(
            device_id=device_id,
            snaps=snap_data,
            total_count=len(snap_data),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list device snaps: {str(e)}"
        )


@router.get("/devices/{device_id}/snaps/{snap_name}", response_model=SnapInfoResponse)
async def get_device_snap_info(
    device_id: str,
    snap_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get information about a specific snap on a device"""
    try:
        snap = await snapd_service.get_device_snap_info(device_id, snap_name)
        
        return SnapInfoResponse(
            device_id=device_id,
            snap_name=snap.name,
            version=snap.version,
            revision=snap.revision,
            status=snap.status,
            channel=snap.channel,
            installed_size=snap.installed_size,
            install_date=snap.install_date,
            summary=snap.summary,
            description=snap.description,
            developer=snap.developer,
            contact=snap.contact,
            website=snap.website,
            license=snap.license,
            tracking_channel=snap.tracking_channel,
            refresh_date=snap.refresh_date,
            cohort_key=snap.cohort_key,
            timestamp=datetime.utcnow()
        )
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snap '{snap_name}' not found on device {device_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get snap info: {str(e)}"
        )


@router.post("/devices/{device_id}/snaps/install", response_model=SnapInstallResponse)
async def install_snap_on_device(
    device_id: str,
    request: SnapInstallRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Install a snap on a device"""
    try:
        change_id = await snapd_service.install_snap_on_device(
            device_id=device_id,
            snap_name=request.snap_name,
            channel=request.channel,
            classic=request.classic,
            dangerous=request.dangerous
        )
        
        return SnapInstallResponse(
            device_id=device_id,
            snap_name=request.snap_name,
            change_id=change_id,
            channel=request.channel,
            status="installing",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install snap: {str(e)}"
        )


@router.post("/devices/{device_id}/snaps/refresh", response_model=SnapRefreshResponse)
async def refresh_snap_on_device(
    device_id: str,
    request: SnapRefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh a snap on a device"""
    try:
        change_id = await snapd_service.refresh_snap_on_device(
            device_id=device_id,
            snap_name=request.snap_name,
            channel=request.channel
        )
        
        return SnapRefreshResponse(
            device_id=device_id,
            snap_name=request.snap_name,
            change_id=change_id,
            channel=request.channel,
            status="refreshing",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh snap: {str(e)}"
        )


@router.post("/devices/{device_id}/snaps/remove", response_model=SnapRemoveResponse)
async def remove_snap_from_device(
    device_id: str,
    request: SnapRemoveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a snap from a device"""
    try:
        change_id = await snapd_service.remove_snap_from_device(
            device_id=device_id,
            snap_name=request.snap_name,
            purge=request.purge
        )
        
        return SnapRemoveResponse(
            device_id=device_id,
            snap_name=request.snap_name,
            change_id=change_id,
            purge=request.purge,
            status="removing",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove snap: {str(e)}"
        )


@router.post("/devices/{device_id}/snaps/{snap_name}/revert")
async def revert_snap_on_device(
    device_id: str,
    snap_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revert a snap to previous revision on a device"""
    try:
        connection = await snapd_service.get_connection(device_id)
        change_id = await connection.revert_snap(snap_name)
        
        # Broadcast revert started event
        await ws_manager.broadcast(json.dumps({
            "type": "snap_revert_started",
            "device_id": device_id,
            "snap_name": snap_name,
            "change_id": change_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {
            "device_id": device_id,
            "snap_name": snap_name,
            "change_id": change_id,
            "status": "reverting",
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revert snap: {str(e)}"
        )


@router.post("/devices/{device_id}/snaps/{snap_name}/enable")
async def enable_snap_on_device(
    device_id: str,
    snap_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enable a snap on a device"""
    try:
        connection = await snapd_service.get_connection(device_id)
        change_id = await connection.enable_snap(snap_name)
        
        return {
            "device_id": device_id,
            "snap_name": snap_name,
            "change_id": change_id,
            "status": "enabling",
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable snap: {str(e)}"
        )


@router.post("/devices/{device_id}/snaps/{snap_name}/disable")
async def disable_snap_on_device(
    device_id: str,
    snap_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable a snap on a device"""
    try:
        connection = await snapd_service.get_connection(device_id)
        change_id = await connection.disable_snap(snap_name)
        
        return {
            "device_id": device_id,
            "snap_name": snap_name,
            "change_id": change_id,
            "status": "disabling",
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable snap: {str(e)}"
        )


@router.get("/devices/{device_id}/changes")
async def list_device_changes(
    device_id: str,
    snap_name: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List changes on a device"""
    try:
        changes = await snapd_service.get_device_changes(device_id, snap_name)
        
        # Limit results
        if limit:
            changes = changes[:limit]
            
        change_data = []
        for change in changes:
            change_data.append({
                'id': change.id,
                'kind': change.kind,
                'summary': change.summary,
                'status': change.status,
                'ready': change.ready,
                'spawn_time': change.spawn_time,
                'ready_time': change.ready_time,
                'error': change.err,
                'task_count': len(change.tasks)
            })
            
        return {
            "device_id": device_id,
            "changes": change_data,
            "total_count": len(change_data),
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list changes: {str(e)}"
        )


@router.get("/devices/{device_id}/changes/{change_id}", response_model=SnapChangeResponse)
async def get_device_change_status(
    device_id: str,
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get status of a specific change on a device"""
    try:
        change = await snapd_service.get_device_change_status(device_id, change_id)
        
        return SnapChangeResponse(
            device_id=device_id,
            change_id=change.id,
            kind=change.kind,
            summary=change.summary,
            status=change.status,
            ready=change.ready,
            spawn_time=change.spawn_time,
            ready_time=change.ready_time,
            error=change.err,
            tasks=[
                {
                    'id': task.get('id'),
                    'kind': task.get('kind'),
                    'summary': task.get('summary'),
                    'status': task.get('status'),
                    'progress': task.get('progress', {}),
                }
                for task in change.tasks
            ],
            timestamp=datetime.utcnow()
        )
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change '{change_id}' not found on device {device_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get change status: {str(e)}"
        )


@router.get("/devices/{device_id}/connections")
async def get_device_connections(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get snap interface connections on a device"""
    try:
        connection = await snapd_service.get_connection(device_id)
        connections = await connection.get_connections()
        
        return {
            "device_id": device_id,
            "connections": connections,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connections: {str(e)}"
        )


@router.post("/devices/{device_id}/connections/connect", response_model=InterfaceConnectionResponse)
async def connect_interface_on_device(
    device_id: str,
    request: InterfaceConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Connect a snap interface on a device"""
    try:
        connection = await snapd_service.get_connection(device_id)
        change_id = await connection.connect_interface(request.plug, request.slot)
        
        return InterfaceConnectionResponse(
            device_id=device_id,
            plug=request.plug,
            slot=request.slot,
            change_id=change_id,
            action="connect",
            status="connecting",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect interface: {str(e)}"
        )


@router.post("/devices/{device_id}/connections/disconnect", response_model=InterfaceConnectionResponse)
async def disconnect_interface_on_device(
    device_id: str,
    request: InterfaceConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect a snap interface on a device"""
    try:
        connection = await snapd_service.get_connection(device_id)
        change_id = await connection.disconnect_interface(request.plug, request.slot)
        
        return InterfaceConnectionResponse(
            device_id=device_id,
            plug=request.plug,
            slot=request.slot,
            change_id=change_id,
            action="disconnect",
            status="disconnecting",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect interface: {str(e)}"
        )


@router.post("/bulk-operations", response_model=BulkSnapOperationResponse)
async def perform_bulk_snap_operation(
    request: BulkSnapOperationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform bulk snap operations across multiple devices"""
    try:
        if not request.device_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No devices specified for bulk operation"
            )
            
        if not request.snap_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No snaps specified for bulk operation"
            )
            
        operation_id = f"bulk_{request.operation}_{datetime.utcnow().timestamp()}"
        results = []
        
        # Execute operation on each device
        for device_id in request.device_ids:
            for snap_name in request.snap_names:
                try:
                    if request.operation == "install":
                        change_id = await snapd_service.install_snap_on_device(
                            device_id, snap_name, request.channel, 
                            request.classic, request.dangerous
                        )
                    elif request.operation == "refresh":
                        change_id = await snapd_service.refresh_snap_on_device(
                            device_id, snap_name, request.channel
                        )
                    elif request.operation == "remove":
                        change_id = await snapd_service.remove_snap_from_device(
                            device_id, snap_name, request.purge
                        )
                    else:
                        raise ValueError(f"Unsupported operation: {request.operation}")
                        
                    results.append({
                        'device_id': device_id,
                        'snap_name': snap_name,
                        'change_id': change_id,
                        'status': 'started',
                        'error': None
                    })
                    
                except Exception as e:
                    results.append({
                        'device_id': device_id,
                        'snap_name': snap_name,
                        'change_id': None,
                        'status': 'failed',
                        'error': str(e)
                    })
                    
        # Broadcast bulk operation started event
        await ws_manager.broadcast(json.dumps({
            "type": "bulk_snap_operation_started",
            "operation_id": operation_id,
            "operation": request.operation,
            "device_count": len(request.device_ids),
            "snap_count": len(request.snap_names),
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return BulkSnapOperationResponse(
            operation_id=operation_id,
            operation=request.operation,
            total_operations=len(request.device_ids) * len(request.snap_names),
            successful_operations=len([r for r in results if r['status'] == 'started']),
            failed_operations=len([r for r in results if r['status'] == 'failed']),
            results=results,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk operation: {str(e)}"
        )


@router.get("/health")
async def snapd_service_health():
    """Check snapd service health"""
    try:
        # Basic health check
        active_connections = len(snapd_service.connections)
        registered_devices = len(snapd_service.device_endpoints)
        
        return {
            "status": "healthy",
            "active_connections": active_connections,
            "registered_devices": registered_devices,
            "service_running": snapd_service.running,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }