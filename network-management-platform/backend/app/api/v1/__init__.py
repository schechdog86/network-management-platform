"""
API v1 routes for Network Management Platform
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .devices import router as devices_router
from .network import router as network_router
from .ssh import router as ssh_router
from .ssh_keys import router as ssh_keys_router
from .backup import router as backup_router
from .ray_cluster import router as ray_router
from .ray_worker import router as ray_worker_router
from .ai import router as ai_router
from .websocket import router as websocket_router
from .snmp import router as snmp_router
from .wake_on_lan import router as wol_router
from .metrics import router as metrics_router
from .pxe import router as pxe_router
from .predictive_maintenance import router as predictive_router
from .github import router as github_router
from .cicd import router as cicd_router
from .webhooks import router as webhooks_router
from .notifications import router as notifications_router
from .alerts import router as alerts_router
from .gpu_optimization import router as gpu_optimization_router

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(devices_router, prefix="/devices", tags=["devices"])
api_router.include_router(network_router, prefix="/network", tags=["network"])
api_router.include_router(ssh_router, prefix="/ssh", tags=["ssh-management"])
api_router.include_router(ssh_keys_router, prefix="/ssh-keys", tags=["ssh-keys"])
api_router.include_router(backup_router, prefix="/backup", tags=["backup"])
api_router.include_router(ray_router, prefix="/ray", tags=["ray-cluster"])
api_router.include_router(ray_worker_router, prefix="/ray-worker", tags=["ray-worker"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai-assistant"])
api_router.include_router(websocket_router, prefix="/websocket", tags=["websocket"])
api_router.include_router(snmp_router, prefix="/snmp", tags=["snmp-monitoring"])
api_router.include_router(wol_router, prefix="/wake-on-lan", tags=["wake-on-lan"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["system-metrics"])
api_router.include_router(pxe_router, prefix="/pxe", tags=["pxe-boot"])
api_router.include_router(predictive_router, prefix="/predictive-maintenance", tags=["predictive-maintenance"])
api_router.include_router(github_router, prefix="/github", tags=["github-integration"])
api_router.include_router(cicd_router, prefix="/cicd", tags=["cicd-tracking"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(gpu_optimization_router, prefix="/gpu-optimization", tags=["gpu-optimization"])

__all__ = ["api_router"]