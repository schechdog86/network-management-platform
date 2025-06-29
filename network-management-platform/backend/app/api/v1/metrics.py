"""
System metrics API endpoints
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import logging

from app.services.system_metrics import system_metrics_collector

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/collection/start")
async def start_metrics_collection(
    interval: int = Query(5, ge=1, le=60, description="Collection interval in seconds")
):
    """Start system metrics collection"""
    try:
        success = await system_metrics_collector.start_collection(interval)
        
        if success:
            return {
                "message": "System metrics collection started",
                "interval": interval,
                "status": "active"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start metrics collection")
            
    except Exception as e:
        logger.error(f"Failed to start metrics collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to start metrics collection")


@router.post("/collection/stop")
async def stop_metrics_collection():
    """Stop system metrics collection"""
    try:
        success = await system_metrics_collector.stop_collection()
        
        if success:
            return {
                "message": "System metrics collection stopped",
                "status": "inactive"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to stop metrics collection")
            
    except Exception as e:
        logger.error(f"Failed to stop metrics collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop metrics collection")


@router.get("/collection/status")
async def get_collection_status():
    """Get metrics collection status"""
    try:
        status = system_metrics_collector.get_collection_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get collection status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collection status")


@router.get("/current")
async def get_current_metrics():
    """Get current system metrics"""
    try:
        metrics = await system_metrics_collector.get_current_metrics()
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get current metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve current metrics")


@router.get("/history")
async def get_metrics_history(
    hours: int = Query(1, ge=1, le=24, description="Hours of history to retrieve")
):
    """Get metrics history for specified time period"""
    try:
        history = await system_metrics_collector.get_metrics_history(hours)
        
        return {
            "hours": hours,
            "data_points": len(history),
            "metrics": history
        }
        
    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics history")


@router.get("/summary")
async def get_metrics_summary():
    """Get summarized system metrics"""
    try:
        current_metrics = await system_metrics_collector.get_current_metrics()
        collection_status = system_metrics_collector.get_collection_status()
        
        # Extract key summary data
        summary = {
            "timestamp": current_metrics.get("timestamp"),
            "hostname": current_metrics.get("hostname"),
            "platform": current_metrics.get("platform"),
            "collection_active": collection_status["is_collecting"],
            "cpu": {
                "usage_percent": current_metrics.get("cpu", {}).get("usage_percent", 0),
                "core_count": current_metrics.get("cpu", {}).get("count_logical", 0),
                "frequency_mhz": current_metrics.get("cpu", {}).get("frequency", {}).get("current", 0)
            },
            "memory": {
                "usage_percent": current_metrics.get("memory", {}).get("virtual", {}).get("percent", 0),
                "total_gb": round(current_metrics.get("memory", {}).get("virtual", {}).get("total", 0) / (1024**3), 2),
                "available_gb": round(current_metrics.get("memory", {}).get("virtual", {}).get("available", 0) / (1024**3), 2)
            },
            "disk": {
                "partitions": len(current_metrics.get("disk", {}).get("partitions", [])),
                "total_read_gb": round(current_metrics.get("disk", {}).get("io", {}).get("read_bytes", 0) / (1024**3), 2),
                "total_write_gb": round(current_metrics.get("disk", {}).get("io", {}).get("write_bytes", 0) / (1024**3), 2)
            },
            "network": {
                "interfaces": len(current_metrics.get("network", {}).get("interfaces", {})),
                "total_sent_gb": round(current_metrics.get("network", {}).get("total_io", {}).get("bytes_sent", 0) / (1024**3), 2),
                "total_recv_gb": round(current_metrics.get("network", {}).get("total_io", {}).get("bytes_recv", 0) / (1024**3), 2)
            },
            "system": {
                "uptime_hours": round(current_metrics.get("system", {}).get("uptime_seconds", 0) / 3600, 1),
                "process_count": current_metrics.get("processes", {}).get("total_count", 0),
                "user_count": len(current_metrics.get("system", {}).get("users", []))
            }
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics summary")


@router.get("/cpu")
async def get_cpu_metrics():
    """Get detailed CPU metrics"""
    try:
        current_metrics = await system_metrics_collector.get_current_metrics()
        cpu_metrics = current_metrics.get("cpu", {})
        
        if not cpu_metrics:
            raise HTTPException(status_code=404, detail="CPU metrics not available")
        
        return {
            "timestamp": current_metrics.get("timestamp"),
            "cpu": cpu_metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get CPU metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve CPU metrics")


@router.get("/memory")
async def get_memory_metrics():
    """Get detailed memory metrics"""
    try:
        current_metrics = await system_metrics_collector.get_current_metrics()
        memory_metrics = current_metrics.get("memory", {})
        
        if not memory_metrics:
            raise HTTPException(status_code=404, detail="Memory metrics not available")
        
        return {
            "timestamp": current_metrics.get("timestamp"),
            "memory": memory_metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve memory metrics")


@router.get("/disk")
async def get_disk_metrics():
    """Get detailed disk metrics"""
    try:
        current_metrics = await system_metrics_collector.get_current_metrics()
        disk_metrics = current_metrics.get("disk", {})
        
        if not disk_metrics:
            raise HTTPException(status_code=404, detail="Disk metrics not available")
        
        return {
            "timestamp": current_metrics.get("timestamp"),
            "disk": disk_metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get disk metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve disk metrics")


@router.get("/network")
async def get_network_metrics():
    """Get detailed network metrics"""
    try:
        current_metrics = await system_metrics_collector.get_current_metrics()
        network_metrics = current_metrics.get("network", {})
        
        if not network_metrics:
            raise HTTPException(status_code=404, detail="Network metrics not available")
        
        return {
            "timestamp": current_metrics.get("timestamp"),
            "network": network_metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get network metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve network metrics")


@router.get("/processes")
async def get_process_metrics():
    """Get process metrics"""
    try:
        current_metrics = await system_metrics_collector.get_current_metrics()
        process_metrics = current_metrics.get("processes", {})
        
        if not process_metrics:
            raise HTTPException(status_code=404, detail="Process metrics not available")
        
        return {
            "timestamp": current_metrics.get("timestamp"),
            "processes": process_metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get process metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve process metrics")