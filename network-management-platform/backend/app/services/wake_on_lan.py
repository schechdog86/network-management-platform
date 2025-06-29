"""
Wake-on-LAN service for remote device management
"""

import asyncio
import logging
import socket
import struct
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import re

from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class WakeOnLANService:
    """Advanced Wake-on-LAN service with verification and monitoring"""
    
    def __init__(self):
        self.magic_packet_cache: Dict[str, bytes] = {}
        
    def _validate_mac_address(self, mac_address: str) -> str:
        """Validate and normalize MAC address format"""
        # Remove common separators and normalize
        mac_clean = re.sub(r'[:-]', '', mac_address.upper())
        
        # Validate MAC address format
        if not re.match(r'^[0-9A-F]{12}$', mac_clean):
            raise ValueError(f"Invalid MAC address format: {mac_address}")
        
        # Return in standard format
        return ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))
    
    def _create_magic_packet(self, mac_address: str) -> bytes:
        """Create Wake-on-LAN magic packet"""
        try:
            # Validate and normalize MAC address
            mac_normalized = self._validate_mac_address(mac_address)
            
            # Check cache first
            if mac_normalized in self.magic_packet_cache:
                return self.magic_packet_cache[mac_normalized]
            
            # Convert MAC to bytes
            mac_bytes = bytes.fromhex(mac_normalized.replace(':', ''))
            
            # Create magic packet: 6 bytes of 0xFF + 16 repetitions of MAC
            magic_packet = b'\xFF' * 6 + mac_bytes * 16
            
            # Cache the packet
            self.magic_packet_cache[mac_normalized] = magic_packet
            
            return magic_packet
            
        except Exception as e:
            logger.error(f"Failed to create magic packet for MAC {mac_address}: {e}")
            raise
    
    async def send_wake_packet(self, mac_address: str, 
                             broadcast_ip: str = "255.255.255.255",
                             port: int = 9) -> Dict[str, Any]:
        """Send Wake-on-LAN magic packet"""
        try:
            # Create magic packet
            magic_packet = self._create_magic_packet(mac_address)
            
            # Send packet via UDP broadcast
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._send_udp_packet, magic_packet, broadcast_ip, port
            )
            
            # Log the attempt
            logger.info(f"Wake-on-LAN packet sent to {mac_address} via {broadcast_ip}:{port}")
            
            # Cache the wake attempt
            cache_key = f"wol_attempt:{mac_address}"
            attempt_data = {
                "mac_address": mac_address,
                "broadcast_ip": broadcast_ip,
                "port": port,
                "timestamp": datetime.utcnow().isoformat(),
                "success": result["success"]
            }
            await cache_manager.set(cache_key, attempt_data, ttl=300)
            
            return {
                "success": result["success"],
                "mac_address": mac_address,
                "broadcast_ip": broadcast_ip,
                "port": port,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Wake-on-LAN packet sent successfully" if result["success"] else result.get("error", "Failed to send packet")
            }
            
        except Exception as e:
            error_msg = f"Failed to send Wake-on-LAN packet to {mac_address}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "mac_address": mac_address,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _send_udp_packet(self, packet: bytes, broadcast_ip: str, port: int) -> Dict[str, Any]:
        """Send UDP packet (runs in thread executor)"""
        try:
            # Create UDP socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # Enable broadcast
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                
                # Set timeout
                sock.settimeout(5.0)
                
                # Send packet
                bytes_sent = sock.sendto(packet, (broadcast_ip, port))
                
                return {
                    "success": True,
                    "bytes_sent": bytes_sent
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_wake_packet_multiple_interfaces(self, mac_address: str,
                                                 broadcast_ips: List[str] = None,
                                                 ports: List[int] = None) -> Dict[str, Any]:
        """Send Wake-on-LAN packets via multiple network interfaces"""
        if broadcast_ips is None:
            broadcast_ips = ["255.255.255.255"]
        
        if ports is None:
            ports = [9, 7]  # Standard WoL ports
        
        results = []
        success_count = 0
        
        try:
            # Send to all IP/port combinations
            tasks = []
            for broadcast_ip in broadcast_ips:
                for port in ports:
                    task = self.send_wake_packet(mac_address, broadcast_ip, port)
                    tasks.append(task)
            
            # Execute all sends concurrently
            send_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in send_results:
                if isinstance(result, dict):
                    results.append(result)
                    if result.get("success"):
                        success_count += 1
                else:
                    results.append({
                        "success": False,
                        "error": str(result)
                    })
            
            overall_success = success_count > 0
            
            return {
                "success": overall_success,
                "mac_address": mac_address,
                "attempts": len(results),
                "successful_attempts": success_count,
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to send multiple Wake-on-LAN packets: {e}")
            return {
                "success": False,
                "mac_address": mac_address,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def verify_device_wake(self, ip_address: str, timeout: int = 30) -> Dict[str, Any]:
        """Verify if device woke up by pinging it"""
        try:
            # Ping the device to check if it's awake
            loop = asyncio.get_event_loop()
            
            # Wait a bit before first ping
            await asyncio.sleep(2)
            
            start_time = datetime.utcnow()
            end_time = start_time
            
            for attempt in range(timeout):
                result = await loop.run_in_executor(
                    None, self._ping_device, ip_address
                )
                
                if result["success"]:
                    end_time = datetime.utcnow()
                    wake_time = (end_time - start_time).total_seconds()
                    
                    return {
                        "success": True,
                        "ip_address": ip_address,
                        "wake_time_seconds": wake_time,
                        "attempts": attempt + 1,
                        "timestamp": end_time.isoformat()
                    }
                
                await asyncio.sleep(1)
            
            return {
                "success": False,
                "ip_address": ip_address,
                "timeout_seconds": timeout,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Device did not respond within timeout period"
            }
            
        except Exception as e:
            logger.error(f"Failed to verify device wake for {ip_address}: {e}")
            return {
                "success": False,
                "ip_address": ip_address,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _ping_device(self, ip_address: str) -> Dict[str, Any]:
        """Ping device to check if it's responsive"""
        try:
            import subprocess
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", ip_address],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            return {
                "success": result.returncode == 0,
                "response_time": None  # Could parse from output if needed
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def wake_and_verify(self, mac_address: str, ip_address: str,
                            broadcast_ips: List[str] = None,
                            verify_timeout: int = 30) -> Dict[str, Any]:
        """Send Wake-on-LAN packet and verify device wakes up"""
        try:
            # Send wake packet
            wake_result = await self.send_wake_packet_multiple_interfaces(
                mac_address, broadcast_ips
            )
            
            if not wake_result["success"]:
                return {
                    "success": False,
                    "mac_address": mac_address,
                    "ip_address": ip_address,
                    "wake_result": wake_result,
                    "error": "Failed to send Wake-on-LAN packet",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Verify device wakes up
            verify_result = await self.verify_device_wake(ip_address, verify_timeout)
            
            # Broadcast status update via WebSocket
            status_data = {
                "device_ip": ip_address,
                "device_mac": mac_address,
                "wake_successful": wake_result["success"],
                "verification_successful": verify_result["success"],
                "wake_time": verify_result.get("wake_time_seconds"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await websocket_manager.connection_manager.broadcast_to_channel(
                "wake_on_lan", 
                {
                    "type": "wake_on_lan_result",
                    "data": status_data
                }
            )
            
            return {
                "success": verify_result["success"],
                "mac_address": mac_address,
                "ip_address": ip_address,
                "wake_result": wake_result,
                "verify_result": verify_result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed wake and verify for {mac_address}/{ip_address}: {e}")
            return {
                "success": False,
                "mac_address": mac_address,
                "ip_address": ip_address,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def bulk_wake_devices(self, devices: List[Dict[str, str]],
                              verify: bool = True) -> Dict[str, Any]:
        """Wake multiple devices in parallel"""
        try:
            tasks = []
            
            for device in devices:
                mac_address = device.get("mac_address")
                ip_address = device.get("ip_address")
                
                if not mac_address:
                    continue
                
                if verify and ip_address:
                    task = self.wake_and_verify(mac_address, ip_address)
                else:
                    task = self.send_wake_packet_multiple_interfaces(mac_address)
                
                tasks.append(task)
            
            # Execute all wake operations concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            successful = 0
            failed = 0
            device_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, dict):
                    device_results.append(result)
                    if result.get("success"):
                        successful += 1
                    else:
                        failed += 1
                else:
                    device_results.append({
                        "success": False,
                        "error": str(result),
                        "device_index": i
                    })
                    failed += 1
            
            return {
                "success": successful > 0,
                "total_devices": len(devices),
                "successful": successful,
                "failed": failed,
                "results": device_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Bulk wake operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_wake_history(self, mac_address: str = None) -> Dict[str, Any]:
        """Get Wake-on-LAN attempt history"""
        try:
            if mac_address:
                # Get history for specific MAC
                cache_key = f"wol_attempt:{mac_address}"
                history = await cache_manager.get(cache_key)
                return {
                    "mac_address": mac_address,
                    "history": [history] if history else [],
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                # Get all recent attempts - would need to implement cache pattern scanning
                return {
                    "message": "Full history retrieval not implemented yet",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get wake history: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global Wake-on-LAN service instance
wol_service = WakeOnLANService()