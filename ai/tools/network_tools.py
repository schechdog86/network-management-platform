"""
Network-specific tools for LangChain
"""

from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
import subprocess
import socket
import ipaddress
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .base import BaseNetworkTool, NetworkToolInput, CachedToolMixin


class NetworkScanInput(NetworkToolInput):
    """Input for network scanning"""
    network: str = Field(description="Network to scan (e.g., 192.168.1.0/24)")
    scan_type: str = Field(default="ping", description="Type of scan: ping, arp, port")


class NetworkScanTool(BaseNetworkTool, CachedToolMixin):
    """Tool for scanning network and discovering devices"""
    
    name: str = "network_scan"
    description: str = "Scan a network to discover active devices. Returns list of found devices with their IP addresses."
    args_schema: Type[BaseModel] = NetworkScanInput
    
    def _execute(self, network: str, scan_type: str = "ping", timeout: int = 30) -> Dict[str, Any]:
        """Execute network scan"""
        # Check cache first
        cache_key = f"{network}_{scan_type}"
        cached = self.get_cached_result(cache_key)
        if cached:
            return cached
        
        try:
            # Parse network
            net = ipaddress.ip_network(network, strict=False)
            devices = []
            
            if scan_type == "ping":
                devices = self._ping_scan(net, timeout)
            elif scan_type == "arp":
                devices = self._arp_scan(net)
            else:
                return {"error": f"Unknown scan type: {scan_type}"}
            
            result = {
                "network": str(net),
                "scan_type": scan_type,
                "devices_found": len(devices),
                "devices": devices
            }
            
            # Cache result
            self.cache_result(cache_key, result)
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def _ping_scan(self, network: ipaddress.IPv4Network, timeout: int) -> List[Dict[str, str]]:
        """Perform ping scan"""
        devices = []
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            
            for ip in network.hosts():
                future = executor.submit(self._ping_host, str(ip), timeout=1)
                futures.append((str(ip), future))
            
            for ip, future in futures:
                if future.result():
                    devices.append({
                        "ip": ip,
                        "status": "online",
                        "hostname": self._get_hostname(ip)
                    })
        
        return devices
    
    def _ping_host(self, ip: str, timeout: int = 1) -> bool:
        """Ping a single host"""
        try:
            # Use system ping command
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 1)
            return result.returncode == 0
        except:
            return False
    
    def _arp_scan(self, network: ipaddress.IPv4Network) -> List[Dict[str, str]]:
        """Perform ARP scan (requires root on Linux)"""
        try:
            cmd = ["arp-scan", str(network)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return []
            
            devices = []
            for line in result.stdout.split('\n'):
                parts = line.split()
                if len(parts) >= 2 and self._is_valid_ip(parts[0]):
                    devices.append({
                        "ip": parts[0],
                        "mac": parts[1] if len(parts) > 1 else "unknown",
                        "vendor": " ".join(parts[2:]) if len(parts) > 2 else "unknown"
                    })
            
            return devices
        except:
            return []
    
    def _get_hostname(self, ip: str) -> str:
        """Get hostname for IP"""
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return "unknown"
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string is valid IP"""
        try:
            ipaddress.ip_address(ip)
            return True
        except:
            return False


class DeviceStatusInput(BaseModel):
    """Input for device status check"""
    device: str = Field(description="Device hostname or IP address")
    checks: List[str] = Field(
        default=["ping", "services"],
        description="Status checks to perform"
    )


class DeviceStatusTool(BaseNetworkTool):
    """Tool for checking device status"""
    
    name: str = "device_status"
    description: str = "Check the status of a network device including connectivity, services, and resources"
    args_schema: Type[BaseModel] = DeviceStatusInput
    
    def _execute(self, device: str, checks: List[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Check device status"""
        if checks is None:
            checks = ["ping", "services"]
        
        status = {
            "device": device,
            "timestamp": self._get_timestamp(),
            "checks": {}
        }
        
        for check in checks:
            if check == "ping":
                status["checks"]["ping"] = self._check_ping(device)
            elif check == "services":
                status["checks"]["services"] = self._check_services(device)
            elif check == "resources":
                status["checks"]["resources"] = self._check_resources(device)
            elif check == "ports":
                status["checks"]["ports"] = self._check_ports(device)
        
        status["overall_status"] = self._determine_overall_status(status["checks"])
        return status
    
    def _check_ping(self, device: str) -> Dict[str, Any]:
        """Check device ping"""
        try:
            cmd = ["ping", "-c", "4", device]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse ping statistics
                lines = result.stdout.split('\n')
                for line in lines:
                    if "min/avg/max" in line:
                        times = line.split('=')[1].strip().split('/')
                        return {
                            "status": "online",
                            "packet_loss": "0%",
                            "avg_latency": f"{times[1]} ms"
                        }
                
                return {"status": "online"}
            else:
                return {"status": "offline", "error": "No response"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _check_services(self, device: str) -> Dict[str, Any]:
        """Check common services"""
        services = {
            "ssh": 22,
            "http": 80,
            "https": 443,
            "snmp": 161
        }
        
        results = {}
        for service, port in services.items():
            results[service] = self._check_port(device, port)
        
        return results
    
    def _check_port(self, device: str, port: int) -> str:
        """Check if port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((device, port))
            sock.close()
            return "open" if result == 0 else "closed"
        except:
            return "error"
    
    def _check_resources(self, device: str) -> Dict[str, Any]:
        """Check device resources (would use SNMP or SSH in production)"""
        # Placeholder for resource checks
        return {
            "cpu_usage": "45%",
            "memory_usage": "62%",
            "disk_usage": "78%"
        }
    
    def _check_ports(self, device: str) -> Dict[str, str]:
        """Check common ports"""
        common_ports = {
            21: "ftp",
            22: "ssh",
            23: "telnet",
            25: "smtp",
            80: "http",
            443: "https",
            3306: "mysql",
            5432: "postgresql",
            6379: "redis",
            8080: "http-alt"
        }
        
        results = {}
        for port, service in common_ports.items():
            status = self._check_port(device, port)
            if status == "open":
                results[f"{port}/{service}"] = status
        
        return results
    
    def _determine_overall_status(self, checks: Dict[str, Any]) -> str:
        """Determine overall device status"""
        if "ping" in checks and checks["ping"].get("status") == "offline":
            return "offline"
        elif any("error" in str(v) for v in checks.values()):
            return "degraded"
        else:
            return "healthy"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()


class PingInput(BaseModel):
    """Input for ping tool"""
    target: str = Field(description="Target hostname or IP to ping")
    count: int = Field(default=4, description="Number of ping packets")


class PingTool(BaseNetworkTool):
    """Simple ping tool"""
    
    name: str = "ping"
    description: str = "Ping a host to check connectivity and measure latency"
    args_schema: Type[BaseModel] = PingInput
    
    def _execute(self, target: str, count: int = 4, timeout: int = 30) -> Dict[str, Any]:
        """Execute ping"""
        try:
            cmd = ["ping", "-c", str(count), "-W", "2", target]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                # Parse output
                lines = result.stdout.split('\n')
                stats = {}
                
                for line in lines:
                    if "packets transmitted" in line:
                        parts = line.split(',')
                        stats["packets_sent"] = int(parts[0].split()[0])
                        stats["packets_received"] = int(parts[1].split()[0])
                        stats["packet_loss"] = parts[2].strip()
                    elif "min/avg/max" in line:
                        times = line.split('=')[1].strip().split('/')
                        stats["min_latency"] = f"{times[0]} ms"
                        stats["avg_latency"] = f"{times[1]} ms"
                        stats["max_latency"] = f"{times[2]} ms"
                
                return {
                    "target": target,
                    "status": "reachable",
                    "statistics": stats
                }
            else:
                return {
                    "target": target,
                    "status": "unreachable",
                    "error": "No response received"
                }
        except Exception as e:
            return {
                "target": target,
                "status": "error",
                "error": str(e)
            }


class TracerouteInput(BaseModel):
    """Input for traceroute tool"""
    target: str = Field(description="Target hostname or IP")
    max_hops: int = Field(default=30, description="Maximum number of hops")


class TracerouteTool(BaseNetworkTool):
    """Traceroute tool"""
    
    name: str = "traceroute"
    description: str = "Trace the network path to a destination"
    args_schema: Type[BaseModel] = TracerouteInput
    
    def _execute(self, target: str, max_hops: int = 30, timeout: int = 30) -> Dict[str, Any]:
        """Execute traceroute"""
        try:
            cmd = ["traceroute", "-m", str(max_hops), "-w", "2", target]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            hops = []
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].isdigit():
                        hop_num = int(parts[0])
                        hop_info = {
                            "hop": hop_num,
                            "host": parts[1] if parts[1] != "*" else "no response",
                            "ip": parts[2].strip("()") if len(parts) > 2 and parts[2].startswith("(") else None,
                            "latencies": []
                        }
                        
                        # Extract latencies
                        for part in parts[3:]:
                            if "ms" in part:
                                hop_info["latencies"].append(part)
                        
                        hops.append(hop_info)
            
            return {
                "target": target,
                "hops": hops,
                "total_hops": len(hops)
            }
        except Exception as e:
            return {
                "target": target,
                "error": str(e)
            }


class PortScanInput(BaseModel):
    """Input for port scan tool"""
    target: str = Field(description="Target hostname or IP")
    ports: Optional[List[int]] = Field(None, description="Specific ports to scan")
    scan_common: bool = Field(default=True, description="Scan common ports if no ports specified")


class PortScanTool(BaseNetworkTool):
    """Port scanning tool"""
    
    name: str = "port_scan"
    description: str = "Scan ports on a target device to see which services are available"
    args_schema: Type[BaseModel] = PortScanInput
    
    def _execute(self, target: str, ports: List[int] = None, scan_common: bool = True, timeout: int = 30) -> Dict[str, Any]:
        """Execute port scan"""
        if ports is None and scan_common:
            ports = [21, 22, 23, 25, 80, 443, 3306, 5432, 6379, 8080, 8443]
        elif ports is None:
            return {"error": "No ports specified"}
        
        open_ports = []
        closed_ports = []
        
        for port in ports:
            if self._scan_port(target, port):
                service = self._get_service_name(port)
                open_ports.append({
                    "port": port,
                    "service": service,
                    "status": "open"
                })
            else:
                closed_ports.append(port)
        
        return {
            "target": target,
            "scanned_ports": len(ports),
            "open_ports": open_ports,
            "closed_ports_count": len(closed_ports)
        }
    
    def _scan_port(self, host: str, port: int, timeout: int = 2) -> bool:
        """Scan a single port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _get_service_name(self, port: int) -> str:
        """Get common service name for port"""
        services = {
            21: "FTP",
            22: "SSH",
            23: "Telnet",
            25: "SMTP",
            80: "HTTP",
            443: "HTTPS",
            3306: "MySQL",
            5432: "PostgreSQL",
            6379: "Redis",
            8080: "HTTP-Proxy",
            8443: "HTTPS-Alt"
        }
        return services.get(port, "Unknown")