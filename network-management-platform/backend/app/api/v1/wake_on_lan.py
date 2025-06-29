"""
Wake-on-LAN API endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import logging

from app.core.rate_limit import bulk_operation_limiter
from app.services.wake_on_lan import wol_service

router = APIRouter()
logger = logging.getLogger(__name__)


class WakeRequest(BaseModel):
    """Wake-on-LAN request model"""
    mac_address: str = Field(..., description="MAC address of target device")
    ip_address: Optional[str] = Field(None, description="IP address for verification")
    broadcast_ip: str = Field("255.255.255.255", description="Broadcast IP address")
    port: int = Field(9, ge=1, le=65535, description="UDP port number")
    verify: bool = Field(False, description="Verify device wakes up")


class WakeMultipleRequest(BaseModel):
    """Multiple interface Wake-on-LAN request"""
    mac_address: str = Field(..., description="MAC address of target device")
    ip_address: Optional[str] = Field(None, description="IP address for verification")
    broadcast_ips: List[str] = Field(["255.255.255.255"], description="List of broadcast IPs")
    ports: List[int] = Field([9, 7], description="List of UDP ports")
    verify: bool = Field(False, description="Verify device wakes up")
    verify_timeout: int = Field(30, ge=5, le=120, description="Verification timeout in seconds")


class BulkWakeRequest(BaseModel):
    """Bulk Wake-on-LAN request"""
    devices: List[dict] = Field(..., description="List of devices with mac_address and optional ip_address")
    verify: bool = Field(False, description="Verify devices wake up")


@router.post("/wake")
async def wake_device(request: WakeRequest):
    """Send Wake-on-LAN packet to a single device"""
    try:
        if request.verify and request.ip_address:
            # Wake and verify
            result = await wol_service.wake_and_verify(
                mac_address=request.mac_address,
                ip_address=request.ip_address,
                broadcast_ips=[request.broadcast_ip]
            )
        else:
            # Just wake
            result = await wol_service.send_wake_packet(
                mac_address=request.mac_address,
                broadcast_ip=request.broadcast_ip,
                port=request.port
            )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Wake-on-LAN request failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packet")


@router.post("/wake/multiple")
async def wake_device_multiple_interfaces(request: WakeMultipleRequest):
    """Send Wake-on-LAN packet via multiple network interfaces"""
    try:
        if request.verify and request.ip_address:
            # Wake and verify
            result = await wol_service.wake_and_verify(
                mac_address=request.mac_address,
                ip_address=request.ip_address,
                broadcast_ips=request.broadcast_ips,
                verify_timeout=request.verify_timeout
            )
        else:
            # Just wake via multiple interfaces
            result = await wol_service.send_wake_packet_multiple_interfaces(
                mac_address=request.mac_address,
                broadcast_ips=request.broadcast_ips,
                ports=request.ports
            )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Multiple interface wake request failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packets")


@router.post("/wake/bulk", dependencies=[Depends(bulk_operation_limiter)])
async def wake_devices_bulk(
    request: BulkWakeRequest,
    background_tasks: BackgroundTasks
):
    """Wake multiple devices in parallel"""
    try:
        if not request.devices:
            raise HTTPException(status_code=400, detail="No devices specified")
        
        # Validate device data
        for i, device in enumerate(request.devices):
            if "mac_address" not in device:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Device {i} missing mac_address"
                )
        
        result = await wol_service.bulk_wake_devices(
            devices=request.devices,
            verify=request.verify
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk wake request failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to wake devices")


@router.post("/verify/{ip_address}")
async def verify_device_wake(
    ip_address: str,
    timeout: int = 30
):
    """Verify if a device is awake by pinging it"""
    try:
        if timeout < 5 or timeout > 120:
            raise HTTPException(status_code=400, detail="Timeout must be between 5 and 120 seconds")
        
        result = await wol_service.verify_device_wake(ip_address, timeout)
        return result
        
    except Exception as e:
        logger.error(f"Device verification failed for {ip_address}: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify device status")


@router.get("/history")
async def get_wake_history(mac_address: Optional[str] = None):
    """Get Wake-on-LAN attempt history"""
    try:
        history = await wol_service.get_wake_history(mac_address)
        return history
        
    except Exception as e:
        logger.error(f"Failed to get wake history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve wake history")


@router.post("/test/magic-packet")
async def test_magic_packet_creation(mac_address: str):
    """Test magic packet creation for a MAC address"""
    try:
        # This is just for testing - creates the packet but doesn't send it
        magic_packet = wol_service._create_magic_packet(mac_address)
        
        return {
            "mac_address": mac_address,
            "magic_packet_size": len(magic_packet),
            "magic_packet_hex": magic_packet.hex(),
            "valid": len(magic_packet) == 102,  # 6 + 6*16 = 102 bytes
            "message": "Magic packet created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Magic packet test failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create magic packet")


@router.get("/broadcast-ips")
async def get_suggested_broadcast_ips():
    """Get suggested broadcast IP addresses for the current network"""
    try:
        import psutil
        import ipaddress
        
        suggested_ips = ["255.255.255.255"]  # Global broadcast
        
        # Get network interfaces
        for interface_name, interface_addresses in psutil.net_if_addrs().items():
            for addr in interface_addresses:
                if addr.family == 2:  # AF_INET (IPv4)
                    try:
                        network = ipaddress.IPv4Network(
                            f"{addr.address}/{addr.netmask}", 
                            strict=False
                        )
                        broadcast = str(network.broadcast_address)
                        if broadcast not in suggested_ips:
                            suggested_ips.append(broadcast)
                    except:
                        pass
        
        return {
            "suggested_broadcast_ips": suggested_ips,
            "recommended_ports": [9, 7],
            "note": "Use 255.255.255.255 for global broadcast, or specific subnet broadcasts for targeted delivery"
        }
        
    except Exception as e:
        logger.error(f"Failed to get broadcast IPs: {e}")
        return {
            "suggested_broadcast_ips": ["255.255.255.255"],
            "recommended_ports": [9, 7],
            "error": "Failed to detect network interfaces"
        }