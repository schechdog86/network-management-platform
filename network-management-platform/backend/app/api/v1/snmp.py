"""
SNMP monitoring API endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.database import get_db
from app.services.snmp_service import snmp_service
from app.schemas.device import DeviceResponse
from app.models.device import Device
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/test")
async def test_snmp_connectivity(
    ip_address: str,
    community: str = "public",
    version: int = 2,
    port: int = 161
):
    """Test SNMP connectivity to a device"""
    try:
        result = await snmp_service.test_snmp_connectivity(
            ip_address=ip_address,
            community=community,
            version=version,
            port=port
        )
        return result
    except Exception as e:
        logger.error(f"SNMP connectivity test failed: {e}")
        raise HTTPException(status_code=500, detail="SNMP test failed")


@router.post("/monitor/{device_id}/start")
async def start_device_monitoring(
    device_id: str,
    interval: int = Query(300, ge=60, le=3600),  # 1 minute to 1 hour
    db: AsyncSession = Depends(get_db)
):
    """Start SNMP monitoring for a device"""
    try:
        success = await snmp_service.start_device_monitoring(device_id, db, interval)
        
        if success:
            return {
                "message": f"SNMP monitoring started for device {device_id}",
                "device_id": device_id,
                "interval": interval
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail="Failed to start SNMP monitoring - device not found or SNMP not enabled"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start SNMP monitoring for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start SNMP monitoring")


@router.post("/monitor/{device_id}/stop")
async def stop_device_monitoring(device_id: str):
    """Stop SNMP monitoring for a device"""
    try:
        success = await snmp_service.stop_device_monitoring(device_id)
        
        if success:
            return {
                "message": f"SNMP monitoring stopped for device {device_id}",
                "device_id": device_id
            }
        else:
            return {
                "message": f"No active monitoring found for device {device_id}",
                "device_id": device_id
            }
    except Exception as e:
        logger.error(f"Failed to stop SNMP monitoring for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop SNMP monitoring")


@router.get("/monitor/{device_id}/status")
async def get_device_monitoring_status(device_id: str):
    """Get SNMP monitoring status for a specific device"""
    try:
        status = await snmp_service.get_device_snmp_status(device_id)
        return status
    except Exception as e:
        logger.error(f"Failed to get SNMP status for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get monitoring status")


@router.get("/monitor/status")
async def get_all_monitoring_status():
    """Get SNMP monitoring status for all devices"""
    try:
        status = await snmp_service.get_all_monitoring_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get all SNMP monitoring status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get monitoring status")


@router.get("/devices/{device_id}/interfaces/{interface_index}/metrics")
async def get_interface_metrics_history(
    device_id: str,
    interface_index: int,
    hours: int = Query(24, ge=1, le=168)  # 1 hour to 1 week
):
    """Get historical interface metrics for a device"""
    try:
        metrics = await snmp_service.get_interface_metrics_history(
            device_id=device_id,
            interface_index=interface_index,
            hours=hours
        )
        
        if "error" in metrics:
            raise HTTPException(status_code=500, detail=metrics["error"])
        
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get interface metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve interface metrics")


@router.post("/monitor/bulk/start")
async def start_bulk_monitoring(
    device_ids: List[str],
    interval: int = Query(300, ge=60, le=3600),
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start SNMP monitoring for multiple devices"""
    try:
        async def start_monitoring_task():
            results = []
            for device_id in device_ids:
                try:
                    success = await snmp_service.start_device_monitoring(device_id, db, interval)
                    results.append({
                        "device_id": device_id,
                        "success": success,
                        "message": "Monitoring started" if success else "Failed to start monitoring"
                    })
                except Exception as e:
                    results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": str(e)
                    })
            
            logger.info(f"Bulk monitoring start completed: {len(results)} devices processed")
        
        background_tasks.add_task(start_monitoring_task)
        
        return {
            "message": f"Bulk SNMP monitoring started for {len(device_ids)} devices",
            "device_count": len(device_ids),
            "interval": interval
        }
    except Exception as e:
        logger.error(f"Failed to start bulk SNMP monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start bulk monitoring")


@router.post("/monitor/bulk/stop")
async def stop_bulk_monitoring(
    device_ids: List[str],
    background_tasks: BackgroundTasks
):
    """Stop SNMP monitoring for multiple devices"""
    try:
        async def stop_monitoring_task():
            results = []
            for device_id in device_ids:
                try:
                    success = await snmp_service.stop_device_monitoring(device_id)
                    results.append({
                        "device_id": device_id,
                        "success": success,
                        "message": "Monitoring stopped" if success else "No active monitoring found"
                    })
                except Exception as e:
                    results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": str(e)
                    })
            
            logger.info(f"Bulk monitoring stop completed: {len(results)} devices processed")
        
        background_tasks.add_task(stop_monitoring_task)
        
        return {
            "message": f"Bulk SNMP monitoring stopped for {len(device_ids)} devices",
            "device_count": len(device_ids)
        }
    except Exception as e:
        logger.error(f"Failed to stop bulk SNMP monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop bulk monitoring")


@router.get("/devices/snmp-enabled")
async def get_snmp_enabled_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get list of devices with SNMP enabled"""
    try:
        result = await db.execute(
            select(Device).where(Device.snmp_enabled == True)
            .offset(skip).limit(limit)
        )
        
        devices = result.scalars().all()
        
        device_list = []
        for device in devices:
            device_list.append({
                "id": device.id,
                "ip_address": device.ip_address,
                "hostname": device.hostname,
                "snmp_community": device.snmp_community,
                "snmp_version": device.snmp_version,
                "snmp_port": device.snmp_port,
                "snmp_timeout": device.snmp_timeout,
                "status": device.status.value if device.status else "unknown"
            })
        
        return {
            "devices": device_list,
            "total": len(device_list),
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Failed to get SNMP-enabled devices: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve SNMP-enabled devices")