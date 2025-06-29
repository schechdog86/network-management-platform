from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from ...core.database import get_db
from ...core.auth import get_current_user
from ...models.user import User
from ...models.device import Device
from ....ai.main import ai_orchestrator

router = APIRouter()

@router.get("/health/{device_id}")
async def analyze_device_health(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze health of a specific device"""
    try:
        # Verify device exists and user has access
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Analyze health
        health_analysis = await ai_orchestrator.analyze_system_health(device_id)
        
        return health_analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-fleet")
async def analyze_fleet_health(
    device_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze health of multiple devices"""
    try:
        results = {}
        
        for device_id in device_ids:
            # Verify device exists
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                health = await ai_orchestrator.analyze_system_health(device_id)
                results[device_id] = health
            else:
                results[device_id] = {"error": "Device not found"}
        
        # Calculate fleet summary
        total_devices = len(device_ids)
        healthy_devices = sum(1 for r in results.values() 
                            if r.get("status") in ["excellent", "good"])
        at_risk_devices = sum(1 for r in results.values() 
                            if r.get("status") in ["poor", "critical"])
        
        return {
            "fleet_summary": {
                "total_devices": total_devices,
                "healthy_devices": healthy_devices,
                "at_risk_devices": at_risk_devices,
                "health_percentage": round((healthy_devices / total_devices * 100), 2) if total_devices > 0 else 0
            },
            "device_results": results,
            "analyzed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mtbf/{device_id}")
async def predict_mtbf(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Predict Mean Time Between Failures for a device"""
    try:
        # Verify device exists
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Get predictive maintenance agent
        agent = ai_orchestrator.agents[ai_orchestrator.AgentType.PREDICTIVE_MAINTENANCE]
        
        # Predict MTBF
        mtbf_prediction = await agent.predict_mtbf(device_id)
        
        return mtbf_prediction
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/predict-failures")
async def predict_failures(
    device_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Predict failures for multiple devices"""
    try:
        predictions = await ai_orchestrator.predict_failures(device_ids)
        return predictions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/maintenance-schedule")
async def generate_maintenance_schedule(
    device_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate optimized maintenance schedule"""
    try:
        schedule = await ai_orchestrator.generate_maintenance_schedule(device_ids)
        return schedule
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{device_id}")
async def get_maintenance_recommendations(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get maintenance recommendations for a device"""
    try:
        # Analyze health to get recommendations
        health = await ai_orchestrator.analyze_system_health(device_id)
        
        return {
            "device_id": device_id,
            "health_score": health.get("health_score", 0),
            "status": health.get("status", "unknown"),
            "recommendations": health.get("recommendations", []),
            "anomalies": health.get("anomalies", []),
            "predictions": health.get("predictions", []),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends/{device_id}")
async def get_health_trends(
    device_id: str,
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get health trends for a device"""
    try:
        # Get predictive maintenance agent
        agent = ai_orchestrator.agents[ai_orchestrator.AgentType.PREDICTIVE_MAINTENANCE]
        
        # Get historical data
        history = agent.metrics_history.get(device_id, [])
        
        # Filter by days
        if days > 0:
            cutoff = datetime.now().timestamp() - (days * 86400)
            history = [h for h in history 
                      if datetime.fromisoformat(h['timestamp']).timestamp() > cutoff]
        
        # Calculate trends
        if history:
            cpu_trend = [h.get('cpu_percent', 0) for h in history]
            memory_trend = [h.get('memory_percent', 0) for h in history]
            disk_trend = [h.get('disk_percent', 0) for h in history]
            health_scores = [agent._calculate_health_score(h) for h in history]
            
            return {
                "device_id": device_id,
                "period_days": days,
                "data_points": len(history),
                "trends": {
                    "cpu": {
                        "current": cpu_trend[-1] if cpu_trend else 0,
                        "average": sum(cpu_trend) / len(cpu_trend) if cpu_trend else 0,
                        "max": max(cpu_trend) if cpu_trend else 0,
                        "min": min(cpu_trend) if cpu_trend else 0,
                        "values": cpu_trend[-24:]  # Last 24 hours
                    },
                    "memory": {
                        "current": memory_trend[-1] if memory_trend else 0,
                        "average": sum(memory_trend) / len(memory_trend) if memory_trend else 0,
                        "max": max(memory_trend) if memory_trend else 0,
                        "min": min(memory_trend) if memory_trend else 0,
                        "values": memory_trend[-24:]
                    },
                    "disk": {
                        "current": disk_trend[-1] if disk_trend else 0,
                        "average": sum(disk_trend) / len(disk_trend) if disk_trend else 0,
                        "max": max(disk_trend) if disk_trend else 0,
                        "min": min(disk_trend) if disk_trend else 0,
                        "values": disk_trend[-24:]
                    },
                    "health_score": {
                        "current": health_scores[-1] if health_scores else 0,
                        "average": sum(health_scores) / len(health_scores) if health_scores else 0,
                        "max": max(health_scores) if health_scores else 0,
                        "min": min(health_scores) if health_scores else 0,
                        "values": health_scores[-24:]
                    }
                },
                "timestamps": [h['timestamp'] for h in history[-24:]]
            }
        else:
            return {
                "device_id": device_id,
                "period_days": days,
                "data_points": 0,
                "message": "No historical data available"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))