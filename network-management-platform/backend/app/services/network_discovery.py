"""
Network discovery service using nmap and various scanning techniques
"""

import asyncio
import json
import logging
import subprocess
import ipaddress
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import concurrent.futures
import socket

try:
    import nmap
except ImportError:
    nmap = None

from app.core.redis_client import cache_manager
from app.models.device import Device, DeviceStatus
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NetworkDiscovery:
    """Network discovery and scanning service"""
    
    def __init__(self):
        self.nm = nmap.PortScanner() if nmap else None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
    async def discover_network(self, network: str, scan_type: str = "ping") -> Dict[str, Any]:
        """
        Discover devices on network
        
        Args:
            network: Network range (e.g., "192.168.1.0/24")
            scan_type: Type of scan (ping, tcp, udp, comprehensive)
        """
        if not self.nm:
            logger.error("python-nmap not available")
            return {"error": "nmap not available"}
        
        try:
            # Validate network range
            network_obj = ipaddress.ip_network(network, strict=False)
            logger.info(f"Starting {scan_type} scan on {network}")
            
            # Check cache first
            cache_key = f"network_scan:{network}:{scan_type}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                logger.info(f"Returning cached scan results for {network}")
                return cached_result
            
            # Run scan in thread pool
            loop = asyncio.get_event_loop()
            scan_result = await loop.run_in_executor(
                self.executor, self._run_nmap_scan, network, scan_type
            )
            
            # Process results
            devices = []
            for host in scan_result.all_hosts():
                device_info = await self._process_host(host, scan_result[host])
                if device_info:
                    devices.append(device_info)
            
            result = {
                "network": network,
                "scan_type": scan_type,
                "timestamp": datetime.utcnow().isoformat(),
                "devices_found": len(devices),
                "devices": devices,
                "scan_info": {
                    "command": scan_result.command_line(),
                    "scan_stats": scan_result.scanstats()
                }
            }
            
            # Cache results for 5 minutes
            await cache_manager.set(cache_key, result, ttl=300)
            
            logger.info(f"Scan completed: {len(devices)} devices found")
            return result
            
        except Exception as e:
            logger.error(f"Network discovery failed: {e}")
            return {"error": str(e)}
    
    def _run_nmap_scan(self, network: str, scan_type: str) -> nmap.PortScanner:
        """Run nmap scan in thread"""
        try:
            if scan_type == "ping":
                # Ping scan (-sn)
                self.nm.scan(hosts=network, arguments='-sn')
            elif scan_type == "tcp":
                # TCP SYN scan on common ports
                self.nm.scan(hosts=network, ports='22,23,25,53,80,110,443,993,995', arguments='-sS')
            elif scan_type == "udp":
                # UDP scan on common ports (requires root)
                self.nm.scan(hosts=network, ports='53,67,68,123,161,162', arguments='-sU')
            elif scan_type == "comprehensive":
                # Comprehensive scan with OS detection
                self.nm.scan(hosts=network, arguments='-A -T4')
            else:
                # Default ping scan
                self.nm.scan(hosts=network, arguments='-sn')
            
            return self.nm
            
        except Exception as e:
            logger.error(f"Nmap scan failed: {e}")
            raise
    
    async def _process_host(self, host_ip: str, host_data: Dict) -> Optional[Dict[str, Any]]:
        """Process individual host data"""
        try:
            device_info = {
                "ip_address": host_ip,
                "hostname": None,
                "mac_address": None,
                "vendor": None,
                "status": host_data.state(),
                "ports": [],
                "os_info": {},
                "services": [],
                "last_seen": datetime.utcnow().isoformat()
            }
            
            # Get hostname
            if 'hostnames' in host_data and host_data['hostnames']:
                device_info["hostname"] = host_data['hostnames'][0]['name']
            else:
                # Try reverse DNS lookup
                try:
                    hostname = socket.gethostbyaddr(host_ip)[0]
                    device_info["hostname"] = hostname
                except:
                    pass
            
            # Get MAC address and vendor
            if 'addresses' in host_data:
                if 'mac' in host_data['addresses']:
                    device_info["mac_address"] = host_data['addresses']['mac']
                    # Get vendor from MAC
                    vendor = self._get_vendor_from_mac(device_info["mac_address"])
                    if vendor:
                        device_info["vendor"] = vendor
            
            # Process ports
            if 'tcp' in host_data:
                for port, port_data in host_data['tcp'].items():
                    device_info["ports"].append({
                        "port": port,
                        "protocol": "tcp",
                        "state": port_data['state'],
                        "service": port_data.get('name', 'unknown'),
                        "version": port_data.get('version', ''),
                        "product": port_data.get('product', '')
                    })
            
            if 'udp' in host_data:
                for port, port_data in host_data['udp'].items():
                    device_info["ports"].append({
                        "port": port,
                        "protocol": "udp",
                        "state": port_data['state'],
                        "service": port_data.get('name', 'unknown'),
                        "version": port_data.get('version', ''),
                        "product": port_data.get('product', '')
                    })
            
            # OS information
            if 'osmatch' in host_data:
                for os_match in host_data['osmatch']:
                    device_info["os_info"] = {
                        "name": os_match['name'],
                        "accuracy": os_match['accuracy'],
                        "line": os_match['line']
                    }
                    break  # Take first match
            
            return device_info
            
        except Exception as e:
            logger.error(f"Error processing host {host_ip}: {e}")
            return None
    
    def _get_vendor_from_mac(self, mac_address: str) -> Optional[str]:
        """Get vendor from MAC address OUI"""
        # This would typically use an OUI database
        # For now, return None - implement with a proper OUI database
        return None
    
    async def ping_host(self, host: str) -> Dict[str, Any]:
        """Simple ping test for a single host"""
        try:
            # Use system ping command for simple test
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, self._system_ping, host
            )
            
            return {
                "host": host,
                "reachable": result["success"],
                "response_time": result.get("time"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "host": host,
                "reachable": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _system_ping(self, host: str) -> Dict[str, Any]:
        """System ping using subprocess"""
        try:
            # Use ping command (works on both Linux and Windows)
            cmd = ["ping", "-c", "1", "-W", "3", host]  # Linux
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Extract response time from output
                import re
                time_match = re.search(r'time=(\d+\.?\d*)', result.stdout)
                response_time = float(time_match.group(1)) if time_match else None
                
                return {
                    "success": True,
                    "time": response_time,
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "output": result.stderr
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def port_scan(self, host: str, ports: str = "22,23,25,53,80,443") -> Dict[str, Any]:
        """Scan specific ports on a host"""
        if not self.nm:
            return {"error": "nmap not available"}
        
        try:
            cache_key = f"port_scan:{host}:{ports}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return cached_result
            
            loop = asyncio.get_event_loop()
            scan_result = await loop.run_in_executor(
                self.executor, self._run_port_scan, host, ports
            )
            
            if host not in scan_result.all_hosts():
                return {
                    "host": host,
                    "ports": ports,
                    "status": "host_down",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            host_data = scan_result[host]
            open_ports = []
            
            if 'tcp' in host_data:
                for port, port_data in host_data['tcp'].items():
                    if port_data['state'] == 'open':
                        open_ports.append({
                            "port": port,
                            "protocol": "tcp",
                            "service": port_data.get('name', 'unknown'),
                            "version": port_data.get('version', ''),
                            "product": port_data.get('product', '')
                        })
            
            result = {
                "host": host,
                "ports_scanned": ports,
                "open_ports": open_ports,
                "status": host_data.state(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Cache for 2 minutes
            await cache_manager.set(cache_key, result, ttl=120)
            
            return result
            
        except Exception as e:
            logger.error(f"Port scan failed for {host}: {e}")
            return {"error": str(e)}
    
    def _run_port_scan(self, host: str, ports: str) -> nmap.PortScanner:
        """Run port scan in thread"""
        self.nm.scan(hosts=host, ports=ports, arguments='-sS')
        return self.nm
    
    async def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get local network interfaces"""
        try:
            import psutil
            
            interfaces = []
            for interface_name, interface_addresses in psutil.net_if_addrs().items():
                interface_info = {
                    "name": interface_name,
                    "addresses": []
                }
                
                for addr in interface_addresses:
                    if addr.family == socket.AF_INET:  # IPv4
                        interface_info["addresses"].append({
                            "family": "IPv4",
                            "address": addr.address,
                            "netmask": addr.netmask,
                            "broadcast": addr.broadcast
                        })
                    elif addr.family == socket.AF_INET6:  # IPv6
                        interface_info["addresses"].append({
                            "family": "IPv6",
                            "address": addr.address,
                            "netmask": addr.netmask
                        })
                
                # Get interface statistics
                stats = psutil.net_if_stats().get(interface_name)
                if stats:
                    interface_info["is_up"] = stats.isup
                    interface_info["duplex"] = stats.duplex.name if hasattr(stats.duplex, 'name') else str(stats.duplex)
                    interface_info["speed"] = stats.speed
                    interface_info["mtu"] = stats.mtu
                
                interfaces.append(interface_info)
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Failed to get network interfaces: {e}")
            return []
    
    async def traceroute(self, host: str, max_hops: int = 30) -> Dict[str, Any]:
        """Perform traceroute to host"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, self._system_traceroute, host, max_hops
            )
            
            return {
                "host": host,
                "hops": result.get("hops", []),
                "success": result.get("success", False),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "host": host,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _system_traceroute(self, host: str, max_hops: int) -> Dict[str, Any]:
        """System traceroute using subprocess"""
        try:
            cmd = ["traceroute", "-m", str(max_hops), host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            hops = []
            if result.returncode == 0:
                lines = result.stdout.split('\n')[1:]  # Skip header
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('traceroute'):
                        # Parse traceroute output
                        parts = line.split()
                        if len(parts) >= 2:
                            hop_num = parts[0]
                            if hop_num.isdigit():
                                hops.append({
                                    "hop": int(hop_num),
                                    "raw_output": line
                                })
                
                return {
                    "success": True,
                    "hops": hops
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
network_discovery = NetworkDiscovery()