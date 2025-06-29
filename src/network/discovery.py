import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import nmap
import ipaddress
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
import subprocess
import re

logger = logging.getLogger(__name__)

@dataclass
class NetworkDevice:
    """Represents a discovered network device."""
    ip_address: str
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    vendor: Optional[str] = None
    open_ports: List[int] = None
    os_info: Optional[str] = None
    services: Dict[int, str] = None
    last_seen: Optional[datetime] = None
    response_time: Optional[float] = None
    device_type: Optional[str] = None
    
    def __post_init__(self):
        if self.open_ports is None:
            self.open_ports = []
        if self.services is None:
            self.services = {}
        if self.last_seen is None:
            self.last_seen = datetime.now()

class NetworkDiscovery:
    """Advanced network discovery and scanning capabilities."""
    
    def __init__(self, max_workers: int = 20):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.nm = nmap.PortScanner()
        
    async def discover_network(self, network: str, 
                             scan_type: str = "ping") -> List[NetworkDevice]:
        """
        Discover devices on network.
        
        Args:
            network: Network range (e.g., "192.168.1.0/24")
            scan_type: Type of scan ("ping", "quick", "full")
        """
        logger.info(f"Starting network discovery for {network}")
        
        try:
            # Validate network range
            network_obj = ipaddress.ip_network(network, strict=False)
            
            if scan_type == "ping":
                return await self._ping_scan(str(network_obj))
            elif scan_type == "quick":
                return await self._quick_scan(str(network_obj))
            elif scan_type == "full":
                return await self._full_scan(str(network_obj))
            else:
                raise ValueError(f"Unknown scan type: {scan_type}")
                
        except Exception as e:
            logger.error(f"Network discovery failed: {e}")
            return []
    
    async def _ping_scan(self, network: str) -> List[NetworkDevice]:
        """Fast ping-only scan."""
        loop = asyncio.get_event_loop()
        
        def run_scan():
            try:
                self.nm.scan(hosts=network, arguments='-sn')  # Ping scan only
                devices = []
                
                for host in self.nm.all_hosts():
                    if self.nm[host].state() == 'up':
                        device = NetworkDevice(
                            ip_address=host,
                            hostname=self._get_hostname(host),
                            last_seen=datetime.now()
                        )
                        
                        # Get MAC address if available
                        if 'mac' in self.nm[host]['addresses']:
                            device.mac_address = self.nm[host]['addresses']['mac']
                            device.vendor = self._get_vendor_from_mac(device.mac_address)
                        
                        devices.append(device)
                
                return devices
                
            except Exception as e:
                logger.error(f"Ping scan failed: {e}")
                return []
        
        return await loop.run_in_executor(self.executor, run_scan)
    
    async def _quick_scan(self, network: str) -> List[NetworkDevice]:
        """Quick scan with common ports."""
        loop = asyncio.get_event_loop()
        
        def run_scan():
            try:
                # Scan common ports
                self.nm.scan(hosts=network, ports='22,23,53,80,135,139,443,445,993,995')
                devices = []
                
                for host in self.nm.all_hosts():
                    if self.nm[host].state() == 'up':
                        device = self._create_device_from_scan(host)
                        devices.append(device)
                
                return devices
                
            except Exception as e:
                logger.error(f"Quick scan failed: {e}")
                return []
        
        return await loop.run_in_executor(self.executor, run_scan)
    
    async def _full_scan(self, network: str) -> List[NetworkDevice]:
        """Comprehensive scan with OS detection."""
        loop = asyncio.get_event_loop()
        
        def run_scan():
            try:
                # Full scan with OS detection
                self.nm.scan(hosts=network, arguments='-sS -O -sV')
                devices = []
                
                for host in self.nm.all_hosts():
                    if self.nm[host].state() == 'up':
                        device = self._create_device_from_scan(host)
                        
                        # Add OS information
                        if 'osmatch' in self.nm[host]:
                            if self.nm[host]['osmatch']:
                                device.os_info = self.nm[host]['osmatch'][0]['name']
                        
                        devices.append(device)
                
                return devices
                
            except Exception as e:
                logger.error(f"Full scan failed: {e}")
                return []
        
        return await loop.run_in_executor(self.executor, run_scan)
    
    def _create_device_from_scan(self, host: str) -> NetworkDevice:
        """Create NetworkDevice from nmap scan results."""
        device = NetworkDevice(
            ip_address=host,
            hostname=self._get_hostname(host),
            last_seen=datetime.now()
        )
        
        # Get MAC address and vendor
        if 'mac' in self.nm[host]['addresses']:
            device.mac_address = self.nm[host]['addresses']['mac']
            device.vendor = self._get_vendor_from_mac(device.mac_address)
        
        # Get open ports and services
        if 'tcp' in self.nm[host]:
            for port, port_info in self.nm[host]['tcp'].items():
                if port_info['state'] == 'open':
                    device.open_ports.append(port)
                    service_name = port_info.get('name', 'unknown')
                    service_version = port_info.get('version', '')
                    device.services[port] = f"{service_name} {service_version}".strip()
        
        # Determine device type based on open ports and services
        device.device_type = self._determine_device_type(device)
        
        return device
    
    def _get_hostname(self, ip: str) -> Optional[str]:
        """Get hostname for IP address."""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except socket.herror:
            return None
    
    def _get_vendor_from_mac(self, mac: str) -> Optional[str]:
        """Get vendor from MAC address (simplified)."""
        # This would typically use an OUI database
        # For now, return first 3 octets as vendor identifier
        if mac and len(mac) >= 8:
            return mac[:8].upper().replace(':', '-')
        return None
    
    def _determine_device_type(self, device: NetworkDevice) -> str:
        """Determine device type based on open ports and services."""
        open_ports = set(device.open_ports)
        
        # Common device type patterns
        if 22 in open_ports:
            if 80 in open_ports or 443 in open_ports:
                return "Server/Router"
            return "Linux/Unix System"
        elif 3389 in open_ports:
            return "Windows Server"
        elif 135 in open_ports and 445 in open_ports:
            return "Windows Workstation"
        elif 80 in open_ports or 443 in open_ports:
            return "Web Server"
        elif 23 in open_ports:
            return "Network Device"
        elif 161 in open_ports:
            return "SNMP Device"
        else:
            return "Unknown Device"

    async def scan_single_host(self, ip: str, 
                              ports: Optional[List[int]] = None) -> NetworkDevice:
        """Scan a single host in detail."""
        loop = asyncio.get_event_loop()
        
        def run_scan():
            try:
                if ports:
                    port_range = ','.join(map(str, ports))
                    self.nm.scan(hosts=ip, ports=port_range, arguments='-sS -sV')
                else:
                    self.nm.scan(hosts=ip, arguments='-sS -sV -O')
                
                if ip in self.nm.all_hosts():
                    return self._create_device_from_scan(ip)
                else:
                    # Host is down or unreachable
                    return NetworkDevice(
                        ip_address=ip,
                        hostname=self._get_hostname(ip),
                        last_seen=datetime.now()
                    )
                    
            except Exception as e:
                logger.error(f"Single host scan failed for {ip}: {e}")
                return NetworkDevice(ip_address=ip)
        
        return await loop.run_in_executor(self.executor, run_scan)

    async def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get local network interfaces."""
        loop = asyncio.get_event_loop()
        
        def get_interfaces():
            interfaces = []
            try:
                # Use ip command to get interface info
                result = subprocess.run(
                    ['ip', 'addr', 'show'], 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                
                current_interface = None
                for line in result.stdout.split('\n'):
                    # Interface line
                    if re.match(r'^\d+:', line):
                        if current_interface:
                            interfaces.append(current_interface)
                        
                        parts = line.split()
                        interface_name = parts[1].rstrip(':')
                        current_interface = {
                            'name': interface_name,
                            'state': 'UP' if 'UP' in line else 'DOWN',
                            'addresses': []
                        }
                    
                    # IP address line
                    elif current_interface and 'inet' in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            addr_info = {
                                'address': parts[1],
                                'type': parts[0]  # inet or inet6
                            }
                            current_interface['addresses'].append(addr_info)
                
                if current_interface:
                    interfaces.append(current_interface)
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to get network interfaces: {e}")
            
            return interfaces
        
        return await loop.run_in_executor(self.executor, get_interfaces)
    
    def close(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)

# Example usage
async def main():
    """Example usage of network discovery."""
    discovery = NetworkDiscovery()
    
    try:
        # Get local interfaces
        interfaces = await discovery.get_network_interfaces()
        print("Network Interfaces:")
        for iface in interfaces:
            print(f"  {iface['name']}: {iface['state']}")
            for addr in iface['addresses']:
                print(f"    {addr['address']}")
        
        # Discover devices on local network
        devices = await discovery.discover_network("192.168.1.0/24", "quick")
        
        print(f"\nDiscovered {len(devices)} devices:")
        for device in devices:
            print(f"  {device.ip_address} ({device.hostname or 'Unknown'})")
            print(f"    Type: {device.device_type}")
            print(f"    Open ports: {device.open_ports}")
            
    finally:
        discovery.close()

if __name__ == "__main__":
    asyncio.run(main())
