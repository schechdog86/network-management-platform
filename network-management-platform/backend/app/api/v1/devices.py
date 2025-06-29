"""
Device management API endpoints
GPU-accelerated network device discovery and management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import ray
import logging

from app.core.database import get_db
from app.core.ray_cluster import get_ray_manager
from app.core.rate_limit import bulk_operation_limiter
from app.core.validation import validate_request, validate_network_scan, DataValidator
from app.models.device import Device, DeviceMetric
from app.schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceResponse, 
    DeviceMetricResponse, DeviceScanRequest
)
from app.services.device_service import DeviceService
from app.services.network_scanner import NetworkScannerService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[DeviceResponse], 
    summary="List all devices",
    description="Retrieve a paginated list of network devices with optional filtering",
    response_description="List of devices matching the filter criteria",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": [{
                        "id": 1,
                        "ip_address": "192.168.1.100",
                        "hostname": "server-01",
                        "device_type": "server",
                        "status": "online",
                        "vendor": "Dell",
                        "last_seen": "2024-01-01T12:00:00Z"
                    }]
                }
            }
        },
        500: {"description": "Internal server error"}
    }
)
async def get_devices(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of records to return"),
    device_type: Optional[str] = Query(None, description="Filter by device type (router, switch, server, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (online, offline, unknown)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a list of managed network devices.
    
    This endpoint supports pagination and filtering by device type and status.
    Use it to retrieve devices for display in dashboards or for bulk operations.
    
    **Filter Options:**
    - `device_type`: router, switch, server, workstation, firewall, access_point
    - `status`: online, offline, unknown
    """
    try:
        device_service = DeviceService(db)
        devices = await device_service.get_devices(
            skip=skip,
            limit=limit,
            device_type=device_type,
            status=status
        )
        return devices
    except Exception as e:
        logger.error(f"Failed to get devices: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve devices")


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """Get specific device by ID"""
    try:
        device_service = DeviceService(db)
        device = await device_service.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve device")


@router.post("/", response_model=DeviceResponse)
async def create_device(
    device: DeviceCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new device"""
    try:
        device_service = DeviceService(db)
        created_device = await device_service.create_device(device)
        return created_device
    except Exception as e:
        logger.error(f"Failed to create device: {e}")
        raise HTTPException(status_code=500, detail="Failed to create device")


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_update: DeviceUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update device information"""
    try:
        device_service = DeviceService(db)
        updated_device = await device_service.update_device(device_id, device_update)
        if not updated_device:
            raise HTTPException(status_code=404, detail="Device not found")
        return updated_device
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update device")


@router.delete("/{device_id}")
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """Delete device"""
    try:
        device_service = DeviceService(db)
        success = await device_service.delete_device(device_id)
        if not success:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"message": "Device deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete device")


@router.get("/{device_id}/metrics", response_model=List[DeviceMetricResponse])
async def get_device_metrics(
    device_id: str,
    metric_type: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=8760),  # 1 hour to 1 year
    db: AsyncSession = Depends(get_db)
):
    """Get device metrics for specified time period"""
    try:
        device_service = DeviceService(db)
        metrics = await device_service.get_device_metrics(
            device_id=device_id,
            metric_type=metric_type,
            hours=hours
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to get metrics for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve device metrics")


@router.post("/scan", response_model=dict, dependencies=[Depends(bulk_operation_limiter)])
async def scan_network(
    scan_request: DeviceScanRequest,
    background_tasks: BackgroundTasks,
    ray_manager = Depends(get_ray_manager)
):
    """Initiate GPU-accelerated network scan"""
    try:
        # Validate scan request
        validation_errors = []
        
        # Validate each subnet
        for subnet in scan_request.subnets:
            if not DataValidator.validate_ip_address(subnet) and not DataValidator.validate_cidr(subnet):
                validation_errors.append(f"Invalid subnet format: {subnet}. Must be a valid IP address or CIDR notation")
        
        # Validate port range
        if scan_request.port_range:
            # Parse port range (format: "1-1024" or single port "80")
            if '-' in scan_request.port_range:
                try:
                    start_port, end_port = scan_request.port_range.split('-')
                    start_port = int(start_port)
                    end_port = int(end_port)
                    
                    if not (DataValidator.validate_port(start_port) and DataValidator.validate_port(end_port)):
                        validation_errors.append(f"Port range must be between 1-65535")
                    elif start_port > end_port:
                        validation_errors.append(f"Invalid port range: start port ({start_port}) must be less than end port ({end_port})")
                except ValueError:
                    validation_errors.append(f"Invalid port range format: {scan_request.port_range}")
            else:
                # Single port
                try:
                    port = int(scan_request.port_range)
                    if not DataValidator.validate_port(port):
                        validation_errors.append(f"Port must be between 1-65535")
                except ValueError:
                    validation_errors.append(f"Invalid port format: {scan_request.port_range}")
        
        # If there are validation errors, raise HTTPException
        if validation_errors:
            raise HTTPException(
                status_code=422,
                detail={"errors": validation_errors}
            )
        
        if not ray.is_initialized():
            raise HTTPException(status_code=503, detail="Ray cluster not available")
        
        # Get network scanner workers
        scanner_workers = ray_manager.get_worker_pool("network_scanners")
        if not scanner_workers:
            raise HTTPException(status_code=503, detail="No network scanner workers available")
        
        # Start background scan
        scan_service = NetworkScannerService(ray_manager)
        scan_id = await scan_service.start_network_scan(scan_request)
        
        return {
            "scan_id": scan_id,
            "message": "Network scan initiated",
            "subnets": scan_request.subnets,
            "estimated_duration": "5-10 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start network scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate network scan")


@router.get("/scan/{scan_id}")
async def get_scan_status(scan_id: str):
    """Get status of network scan"""
    try:
        scan_service = NetworkScannerService(get_ray_manager())
        status = await scan_service.get_scan_status(scan_id)
        if not status:
            raise HTTPException(status_code=404, detail="Scan not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan status {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scan status")


@router.post("/{device_id}/wake")
async def wake_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """Send Wake-on-LAN magic packet to device"""
    try:
        device_service = DeviceService(db)
        success = await device_service.wake_device(device_id)
        if not success:
            raise HTTPException(status_code=404, detail="Device not found or Wake-on-LAN not supported")
        return {"message": "Wake-on-LAN packet sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to wake device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packet")


@router.post("/{device_id}/reboot")
async def reboot_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """Reboot device via SSH or SNMP"""
    try:
        device_service = DeviceService(db)
        success = await device_service.reboot_device(device_id)
        if not success:
            raise HTTPException(status_code=404, detail="Device not found or reboot not supported")
        return {"message": "Reboot command sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reboot device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reboot device")


@router.get("/{device_id}/status")
async def get_device_status(device_id: str, db: AsyncSession = Depends(get_db)):
    """Get real-time device status"""
    try:
        device_service = DeviceService(db)
        status = await device_service.get_real_time_status(device_id)
        if not status:
            raise HTTPException(status_code=404, detail="Device not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve device status")


@router.post("/bulk-action", dependencies=[Depends(bulk_operation_limiter)])
async def bulk_device_action(
    action: str,
    device_ids: List[str],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Perform bulk action on multiple devices"""
    try:
        if action not in ["wake", "reboot", "scan", "update_status"]:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        device_service = DeviceService(db)
        
        # Start bulk action in background
        background_tasks.add_task(
            device_service.perform_bulk_action,
            action,
            device_ids
        )
        
        return {
            "message": f"Bulk {action} action initiated",
            "device_count": len(device_ids),
            "estimated_duration": "1-5 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform bulk action {action}: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform bulk action")