"""
PXE Boot server API endpoints
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import logging

from app.core.database import get_db
from app.services.pxe_server import pxe_boot_manager, PXEBootManager, BootMode

router = APIRouter()
logger = logging.getLogger(__name__)


class PXEServerConfig(BaseModel):
    """PXE server configuration"""
    interface: str = Field(..., description="Network interface for DHCP")
    subnet: str = Field(..., description="Subnet for DHCP (e.g., 192.168.1.0/24)")
    tftp_server: str = Field(..., description="TFTP server IP address")
    http_server: str = Field(..., description="HTTP server URL")
    tftp_root: str = Field(default="/var/lib/tftpboot", description="TFTP root directory")
    http_root: str = Field(default="/var/www/pxe", description="HTTP root directory")
    tftp_port: int = Field(default=69, description="TFTP port")
    http_port: int = Field(default=8080, description="HTTP port")
    boot_mode: str = Field(default="both", description="Boot mode: bios, uefi, or both")


class DeploymentJobConfig(BaseModel):
    """OS deployment job configuration"""
    target_mac: str = Field(..., description="Target device MAC address")
    os_type: str = Field(..., description="OS type (ubuntu2204, debian12, centos9, etc.)")
    hostname: str = Field(..., description="Hostname for the new system")
    username: Optional[str] = Field(default="admin", description="Username for the new system")
    password_hash: Optional[str] = Field(default=None, description="Password hash")
    ssh_keys: Optional[List[str]] = Field(default=[], description="SSH public keys")
    packages: Optional[List[str]] = Field(default=[], description="Additional packages to install")
    locale: Optional[str] = Field(default="en_US.UTF-8", description="System locale")
    timezone: Optional[str] = Field(default="UTC", description="System timezone")
    keyboard_layout: Optional[str] = Field(default="us", description="Keyboard layout")
    storage_layout: Optional[str] = Field(default="direct", description="Storage layout")
    use_dhcp: Optional[bool] = Field(default=True, description="Use DHCP for network")
    allow_password_auth: Optional[bool] = Field(default=True, description="Allow SSH password auth")
    domain: Optional[str] = Field(default="local", description="Domain name")
    late_commands: Optional[List[str]] = Field(default=[], description="Late commands to run")
    post_commands: Optional[List[str]] = Field(default=[], description="Post-installation commands")


class DHCPReservation(BaseModel):
    """DHCP reservation configuration"""
    mac_address: str = Field(..., description="MAC address")
    ip_address: str = Field(..., description="Reserved IP address")


@router.post("/server/start")
async def start_pxe_server(
    config: PXEServerConfig,
    background_tasks: BackgroundTasks
):
    """Start PXE boot services"""
    try:
        global pxe_boot_manager
        
        # Convert config to dict
        config_dict = config.dict()
        
        # Initialize PXE boot manager if not exists
        if pxe_boot_manager is None:
            pxe_boot_manager = PXEBootManager(config_dict)
        
        # Start services in background
        background_tasks.add_task(pxe_boot_manager.start_services)
        
        return {
            "status": "starting",
            "message": "PXE boot services are starting",
            "config": config_dict
        }
        
    except Exception as e:
        logger.error(f"Failed to start PXE server: {e}")
        raise HTTPException(status_code=500, detail="Failed to start PXE server")


@router.post("/server/stop")
async def stop_pxe_server():
    """Stop PXE boot services"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None:
            raise HTTPException(status_code=400, detail="PXE server not running")
        
        await pxe_boot_manager.stop_services()
        
        return {
            "status": "stopped",
            "message": "PXE boot services stopped successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop PXE server: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop PXE server")


@router.get("/server/status")
async def get_pxe_server_status():
    """Get PXE server status"""
    try:
        from app.core.redis_client import cache_manager
        
        status = await cache_manager.get("pxe_boot_status")
        
        if not status:
            return {
                "status": "stopped",
                "services": {
                    "dhcp": "stopped",
                    "tftp": "stopped",
                    "http": "stopped"
                }
            }
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get PXE server status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get server status")


@router.post("/deployments")
async def create_deployment_job(
    job_config: DeploymentJobConfig,
    background_tasks: BackgroundTasks
):
    """Create OS deployment job"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None:
            raise HTTPException(status_code=400, detail="PXE server not running")
        
        # Create deployment job
        result = await pxe_boot_manager.create_deployment_job(job_config.dict())
        
        if result["success"]:
            return {
                "job_id": result["job_id"],
                "message": result["message"],
                "target_mac": job_config.target_mac,
                "os_type": job_config.os_type,
                "hostname": job_config.hostname
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create deployment job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create deployment job")


@router.get("/deployments/{job_id}")
async def get_deployment_status(job_id: str):
    """Get deployment job status"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None:
            raise HTTPException(status_code=400, detail="PXE server not running")
        
        status = await pxe_boot_manager.get_deployment_status(job_id)
        
        if "error" in status and status["error"] == "Job not found":
            raise HTTPException(status_code=404, detail="Deployment job not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deployment status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get deployment status")


@router.get("/deployments")
async def list_deployment_jobs():
    """List all deployment jobs"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None:
            return {
                "jobs": [],
                "total": 0
            }
        
        jobs = list(pxe_boot_manager.deployment_jobs.values())
        
        return {
            "jobs": jobs,
            "total": len(jobs)
        }
        
    except Exception as e:
        logger.error(f"Failed to list deployment jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list deployment jobs")


@router.post("/dhcp/reservations")
async def add_dhcp_reservation(reservation: DHCPReservation):
    """Add DHCP reservation"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None:
            raise HTTPException(status_code=400, detail="PXE server not running")
        
        if pxe_boot_manager.dhcp_server is None:
            raise HTTPException(status_code=400, detail="DHCP server not running")
        
        # Add reservation
        pxe_boot_manager.dhcp_server.reservations[reservation.mac_address] = reservation.ip_address
        
        # Store in cache
        from app.core.redis_client import cache_manager
        await cache_manager.set(
            f"dhcp_reservation:{reservation.mac_address}",
            {
                "mac_address": reservation.mac_address,
                "ip_address": reservation.ip_address
            },
            ttl=0  # No expiration
        )
        
        return {
            "success": True,
            "message": "DHCP reservation added",
            "mac_address": reservation.mac_address,
            "ip_address": reservation.ip_address
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add DHCP reservation: {e}")
        raise HTTPException(status_code=500, detail="Failed to add reservation")


@router.get("/dhcp/reservations")
async def list_dhcp_reservations():
    """List DHCP reservations"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None or pxe_boot_manager.dhcp_server is None:
            return {
                "reservations": [],
                "total": 0
            }
        
        reservations = [
            {
                "mac_address": mac,
                "ip_address": ip
            }
            for mac, ip in pxe_boot_manager.dhcp_server.reservations.items()
        ]
        
        return {
            "reservations": reservations,
            "total": len(reservations)
        }
        
    except Exception as e:
        logger.error(f"Failed to list DHCP reservations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list reservations")


@router.delete("/dhcp/reservations/{mac_address}")
async def delete_dhcp_reservation(mac_address: str):
    """Delete DHCP reservation"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None or pxe_boot_manager.dhcp_server is None:
            raise HTTPException(status_code=400, detail="DHCP server not running")
        
        # Normalize MAC address
        mac_address = mac_address.replace("-", ":").lower()
        
        if mac_address in pxe_boot_manager.dhcp_server.reservations:
            del pxe_boot_manager.dhcp_server.reservations[mac_address]
            
            # Remove from cache
            from app.core.redis_client import cache_manager
            await cache_manager.delete(f"dhcp_reservation:{mac_address}")
            
            return {
                "success": True,
                "message": "DHCP reservation deleted",
                "mac_address": mac_address
            }
        else:
            raise HTTPException(status_code=404, detail="Reservation not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete DHCP reservation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete reservation")


@router.get("/dhcp/leases")
async def list_dhcp_leases():
    """List active DHCP leases"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None or pxe_boot_manager.dhcp_server is None:
            return {
                "leases": [],
                "total": 0
            }
        
        leases = [
            {
                "mac_address": mac,
                "ip_address": lease["ip"],
                "timestamp": lease["timestamp"].isoformat(),
                "lease_time": lease["lease_time"]
            }
            for mac, lease in pxe_boot_manager.dhcp_server.leases.items()
        ]
        
        return {
            "leases": leases,
            "total": len(leases)
        }
        
    except Exception as e:
        logger.error(f"Failed to list DHCP leases: {e}")
        raise HTTPException(status_code=500, detail="Failed to list leases")


@router.get("/os-images")
async def list_available_os_images():
    """List available OS images for deployment"""
    try:
        # Predefined OS types with metadata
        os_images = [
            {
                "id": "ubuntu2204",
                "name": "Ubuntu 22.04 LTS Server",
                "type": "ubuntu",
                "version": "22.04",
                "architecture": "amd64",
                "install_method": "autoinstall"
            },
            {
                "id": "ubuntu2404",
                "name": "Ubuntu 24.04 LTS Server",
                "type": "ubuntu",
                "version": "24.04",
                "architecture": "amd64",
                "install_method": "autoinstall"
            },
            {
                "id": "debian12",
                "name": "Debian 12 (Bookworm)",
                "type": "debian",
                "version": "12",
                "architecture": "amd64",
                "install_method": "preseed"
            },
            {
                "id": "centos9",
                "name": "CentOS Stream 9",
                "type": "centos",
                "version": "9",
                "architecture": "x86_64",
                "install_method": "kickstart"
            },
            {
                "id": "rhel9",
                "name": "Red Hat Enterprise Linux 9",
                "type": "rhel",
                "version": "9",
                "architecture": "x86_64",
                "install_method": "kickstart"
            }
        ]
        
        return {
            "images": os_images,
            "total": len(os_images)
        }
        
    except Exception as e:
        logger.error(f"Failed to list OS images: {e}")
        raise HTTPException(status_code=500, detail="Failed to list OS images")


@router.post("/test-boot")
async def test_pxe_boot(mac_address: str):
    """Test PXE boot for a specific MAC address"""
    try:
        global pxe_boot_manager
        
        if pxe_boot_manager is None:
            raise HTTPException(status_code=400, detail="PXE server not running")
        
        # Normalize MAC address
        mac_address = mac_address.replace("-", ":").lower()
        
        # Create test deployment job
        test_config = {
            "target_mac": mac_address,
            "os_type": "ubuntu2204",
            "hostname": "pxe-test-node",
            "username": "test",
            "password_hash": "$6$rounds=4096$test$hash"
        }
        
        result = await pxe_boot_manager.create_deployment_job(test_config)
        
        if result["success"]:
            return {
                "success": True,
                "message": "PXE boot test initiated",
                "job_id": result["job_id"],
                "mac_address": mac_address,
                "instructions": "Power on the target device and ensure it's set to network boot"
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test PXE boot: {e}")
        raise HTTPException(status_code=500, detail="Failed to test PXE boot")