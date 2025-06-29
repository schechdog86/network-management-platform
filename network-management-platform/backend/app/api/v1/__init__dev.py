"""
API v1 routes for Network Management Platform (Development)
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .devices import router as devices_router
from .network import router as network_router
from .ssh import router as ssh_router
from .backup import router as backup_router
from .websocket import router as websocket_router
from .snmp import router as snmp_router
from .wake_on_lan import router as wol_router
from .metrics import router as metrics_router
from .pxe import router as pxe_router

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(devices_router, prefix="/devices", tags=["devices"])
api_router.include_router(network_router, prefix="/network", tags=["network"])
api_router.include_router(ssh_router, prefix="/ssh", tags=["ssh-management"])
api_router.include_router(backup_router, prefix="/backup", tags=["backup"])
api_router.include_router(websocket_router, prefix="/websocket", tags=["websocket"])
api_router.include_router(snmp_router, prefix="/snmp", tags=["snmp-monitoring"])
api_router.include_router(wol_router, prefix="/wake-on-lan", tags=["wake-on-lan"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["system-metrics"])
api_router.include_router(pxe_router, prefix="/pxe", tags=["pxe-boot"])

__all__ = ["api_router"]