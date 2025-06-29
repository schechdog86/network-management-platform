import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from pysnmp.hlapi.asyncio import *
from pysnmp.entity.rfc3413.oneliner import cmdgen
import time

logger = logging.getLogger(__name__)

@dataclass
class SNMPDevice:
    """SNMP-enabled network device."""
    ip_address: str
    community: str = "public"
    version: int = 2  # SNMP version (1, 2, or 3)
    port: int = 161
    timeout: int = 5
    retries: int = 3
    # SNMP v3 specific
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None
    
@dataclass
class SystemInfo:
    """System information from SNMP."""
    hostname: Optional[str] = None
    description: Optional[str] = None
    uptime: Optional[int] = None
    contact: Optional[str] = None
    location: Optional[str] = None
    services: Optional[int] = None

@dataclass
class InterfaceInfo:
    """Network interface information."""
    index: int
    name: str
    description: str
    type: int
    mtu: int
    speed: int
    mac_address: str
    admin_status: int
    oper_status: int
    in_octets: int = 0
    out_octets: int = 0
    in_errors: int = 0
    out_errors: int = 0
    last_change: int = 0

class SNMPManager:
    """Advanced SNMP management and monitoring."""
    
    # Common OIDs
    SYSTEM_OIDS = {
        'sysDescr': '1.3.6.1.2.1.1.1.0',
        'sysObjectID': '1.3.6.1.2.1.1.2.0',
        'sysUpTime': '1.3.6.1.2.1.1.3.0',
        'sysContact': '1.3.6.1.2.1.1.4.0',
        'sysName': '1.3.6.1.2.1.1.5.0',
        'sysLocation': '1.3.6.1.2.1.1.6.0',
        'sysServices': '1.3.6.1.2.1.1.7.0'
    }
    
    INTERFACE_OIDS = {
        'ifIndex': '1.3.6.1.2.1.2.2.1.1',
        'ifDescr': '1.3.6.1.2.1.2.2.1.2',
        'ifType': '1.3.6.1.2.1.2.2.1.3',
        'ifMtu': '1.3.6.1.2.1.2.2.1.4',
        'ifSpeed': '1.3.6.1.2.1.2.2.1.5',
        'ifPhysAddress': '1.3.6.1.2.1.2.2.1.6',
        'ifAdminStatus': '1.3.6.1.2.1.2.2.1.7',
        'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',
        'ifLastChange': '1.3.6.1.2.1.2.2.1.9',
        'ifInOctets': '1.3.6.1.2.1.2.2.1.10',
        'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',
        'ifInErrors': '1.3.6.1.2.1.2.2.1.14',
        'ifOutErrors': '1.3.6.1.2.1.2.2.1.20'
    }
    
    CPU_OIDS = {
        'hrProcessorLoad': '1.3.6.1.2.1.25.3.3.1.2',  # Host Resources MIB
        'cpmCPUTotal5min': '1.3.6.1.4.1.9.9.109.1.1.1.1.8'  # Cisco specific
    }
    
    MEMORY_OIDS = {
        'hrMemorySize': '1.3.6.1.2.1.25.2.2',
        'hrStorageUsed': '1.3.6.1.2.1.25.2.3.1.6',
        'hrStorageSize': '1.3.6.1.2.1.25.2.3.1.5'
    }
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def get_system_info(self, device: SNMPDevice) -> Optional[SystemInfo]:
        """Get basic system information via SNMP."""
        try:
            values = await self._get_multiple_oids(device, list(self.SYSTEM_OIDS.values()))
            
            if values:
                return SystemInfo(
                    description=values.get(self.SYSTEM_OIDS['sysDescr']),
                    hostname=values.get(self.SYSTEM_OIDS['sysName']),
                    uptime=self._parse_int(values.get(self.SYSTEM_OIDS['sysUpTime'])),
                    contact=values.get(self.SYSTEM_OIDS['sysContact']),
                    location=values.get(self.SYSTEM_OIDS['sysLocation']),
                    services=self._parse_int(values.get(self.SYSTEM_OIDS['sysServices']))
                )
        except Exception as e:
            logger.error(f"Failed to get system info from {device.ip_address}: {e}")
        
        return None
    
    async def get_interfaces(self, device: SNMPDevice) -> List[InterfaceInfo]:
        """Get network interface information."""
        interfaces = []
        
        try:
            # Get interface count first
            interface_indices = await self._walk_oid(device, self.INTERFACE_OIDS['ifIndex'])
            
            for index_oid, index_value in interface_indices:
                index = int(index_value)
                
                # Get interface details
                interface_data = {}
                for name, base_oid in self.INTERFACE_OIDS.items():
                    if name != 'ifIndex':
                        oid = f"{base_oid}.{index}"
                        value = await self._get_single_oid(device, oid)
                        interface_data[name] = value
                
                # Create interface object
                if interface_data.get('ifDescr'):
                    interface = InterfaceInfo(
                        index=index,
                        name=str(interface_data.get('ifDescr', '')),
                        description=str(interface_data.get('ifDescr', '')),
                        type=self._parse_int(interface_data.get('ifType', 0)),
                        mtu=self._parse_int(interface_data.get('ifMtu', 0)),
                        speed=self._parse_int(interface_data.get('ifSpeed', 0)),
                        mac_address=self._format_mac(interface_data.get('ifPhysAddress', '')),
                        admin_status=self._parse_int(interface_data.get('ifAdminStatus', 0)),
                        oper_status=self._parse_int(interface_data.get('ifOperStatus', 0)),
                        in_octets=self._parse_int(interface_data.get('ifInOctets', 0)),
                        out_octets=self._parse_int(interface_data.get('ifOutOctets', 0)),
                        in_errors=self._parse_int(interface_data.get('ifInErrors', 0)),
                        out_errors=self._parse_int(interface_data.get('ifOutErrors', 0)),
                        last_change=self._parse_int(interface_data.get('ifLastChange', 0))
                    )
                    interfaces.append(interface)
        
        except Exception as e:
            logger.error(f"Failed to get interfaces from {device.ip_address}: {e}")
        
        return interfaces
    
    async def get_cpu_usage(self, device: SNMPDevice) -> Optional[float]:
        """Get CPU usage percentage."""
        try:
            # Try Host Resources MIB first
            cpu_loads = await self._walk_oid(device, self.CPU_OIDS['hrProcessorLoad'])
            if cpu_loads:
                # Calculate average CPU load
                total_load = sum(int(load[1]) for load in cpu_loads)
                avg_load = total_load / len(cpu_loads)
                return float(avg_load)
            
            # Try Cisco specific OID
            cisco_cpu = await self._get_single_oid(device, self.CPU_OIDS['cpmCPUTotal5min'])
            if cisco_cpu:
                return float(cisco_cpu)
                
        except Exception as e:
            logger.error(f"Failed to get CPU usage from {device.ip_address}: {e}")
        
        return None
    
    async def get_memory_usage(self, device: SNMPDevice) -> Optional[Dict[str, int]]:
        """Get memory usage information."""
        try:
            memory_info = {}
            
            # Get memory storage entries
            storage_indices = await self._walk_oid(device, '1.3.6.1.2.1.25.2.3.1.1')
            
            total_memory = 0
            used_memory = 0
            
            for index_oid, index_value in storage_indices:
                index = index_value
                
                # Get storage type (2 = RAM)
                type_oid = f"1.3.6.1.2.1.25.2.3.1.2.{index}"
                storage_type = await self._get_single_oid(device, type_oid)
                
                if storage_type and "1.3.6.1.2.1.25.2.1.2" in str(storage_type):  # RAM type
                    # Get allocation unit size
                    unit_oid = f"1.3.6.1.2.1.25.2.3.1.4.{index}"
                    unit_size = self._parse_int(await self._get_single_oid(device, unit_oid))
                    
                    # Get total and used units
                    size_oid = f"1.3.6.1.2.1.25.2.3.1.5.{index}"
                    used_oid = f"1.3.6.1.2.1.25.2.3.1.6.{index}"
                    
                    total_units = self._parse_int(await self._get_single_oid(device, size_oid))
                    used_units = self._parse_int(await self._get_single_oid(device, used_oid))
                    
                    if unit_size and total_units and used_units:
                        total_memory += total_units * unit_size
                        used_memory += used_units * unit_size
            
            if total_memory > 0:
                return {
                    'total': total_memory,
                    'used': used_memory,
                    'free': total_memory - used_memory,
                    'usage_percent': round((used_memory / total_memory) * 100, 2)
                }
                
        except Exception as e:
            logger.error(f"Failed to get memory usage from {device.ip_address}: {e}")
        
        return None
    
    async def monitor_device(self, device: SNMPDevice, 
                           interval: int = 60) -> Dict[str, Any]:
        """Continuously monitor device metrics."""
        monitoring_data = {
            'device': device.ip_address,
            'timestamp': datetime.now().isoformat(),
            'system_info': None,
            'interfaces': [],
            'cpu_usage': None,
            'memory_usage': None,
            'uptime': None
        }
        
        try:
            # Get all monitoring data
            monitoring_data['system_info'] = await self.get_system_info(device)
            monitoring_data['interfaces'] = await self.get_interfaces(device)
            monitoring_data['cpu_usage'] = await self.get_cpu_usage(device)
            monitoring_data['memory_usage'] = await self.get_memory_usage(device)
            
            if monitoring_data['system_info']:
                monitoring_data['uptime'] = monitoring_data['system_info'].uptime
                
        except Exception as e:
            logger.error(f"Monitoring failed for {device.ip_address}: {e}")
            monitoring_data['error'] = str(e)
        
        return monitoring_data
    
    async def _get_single_oid(self, device: SNMPDevice, oid: str) -> Optional[str]:
        """Get single OID value."""
        try:
            if device.version == 3:
                # SNMP v3
                iterator = getCmd(
                    SnmpEngine(),
                    UsmUserData(device.username, device.auth_password, device.priv_password),
                    UdpTransportTarget((device.ip_address, device.port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )
            else:
                # SNMP v1/v2c
                iterator = getCmd(
                    SnmpEngine(),
                    CommunityData(device.community, mpModel=device.version-1),
                    UdpTransportTarget((device.ip_address, device.port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )
            
            errorIndication, errorStatus, errorIndex, varBinds = await iterator
            
            if errorIndication:
                logger.error(f"SNMP error: {errorIndication}")
                return None
            elif errorStatus:
                logger.error(f"SNMP error: {errorStatus.prettyPrint()}")
                return None
            else:
                for varBind in varBinds:
                    return str(varBind[1])
                    
        except Exception as e:
            logger.error(f"SNMP get failed for {device.ip_address} OID {oid}: {e}")
        
        return None
    
    async def _get_multiple_oids(self, device: SNMPDevice, 
                                oids: List[str]) -> Dict[str, str]:
        """Get multiple OID values in one request."""
        result = {}
        
        try:
            object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
            
            if device.version == 3:
                iterator = getCmd(
                    SnmpEngine(),
                    UsmUserData(device.username, device.auth_password, device.priv_password),
                    UdpTransportTarget((device.ip_address, device.port)),
                    ContextData(),
                    *object_types
                )
            else:
                iterator = getCmd(
                    SnmpEngine(),
                    CommunityData(device.community, mpModel=device.version-1),
                    UdpTransportTarget((device.ip_address, device.port)),
                    ContextData(),
                    *object_types
                )
            
            errorIndication, errorStatus, errorIndex, varBinds = await iterator
            
            if not errorIndication and not errorStatus:
                for i, varBind in enumerate(varBinds):
                    result[oids[i]] = str(varBind[1])
                    
        except Exception as e:
            logger.error(f"SNMP bulk get failed for {device.ip_address}: {e}")
        
        return result
    
    async def _walk_oid(self, device: SNMPDevice, oid: str) -> List[tuple]:
        """Walk OID tree and return all values."""
        result = []
        
        try:
            if device.version == 3:
                iterator = nextCmd(
                    SnmpEngine(),
                    UsmUserData(device.username, device.auth_password, device.priv_password),
                    UdpTransportTarget((device.ip_address, device.port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicMode=False
                )
            else:
                iterator = nextCmd(
                    SnmpEngine(),
                    CommunityData(device.community, mpModel=device.version-1),
                    UdpTransportTarget((device.ip_address, device.port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicMode=False
                )
            
            async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication:
                    break
                elif errorStatus:
                    break
                else:
                    for varBind in varBinds:
                        result.append((str(varBind[0]), str(varBind[1])))
                        
        except Exception as e:
            logger.error(f"SNMP walk failed for {device.ip_address} OID {oid}: {e}")
        
        return result
    
    def _parse_int(self, value: Any) -> int:
        """Safely parse integer value."""
        try:
            if value is None:
                return 0
            return int(str(value))
        except (ValueError, TypeError):
            return 0
    
    def _format_mac(self, mac_bytes: Any) -> str:
        """Format MAC address from bytes."""
        try:
            if isinstance(mac_bytes, str):
                # Convert hex string to MAC format
                mac_hex = mac_bytes.replace(' ', '').replace('0x', '')
                if len(mac_hex) == 12:
                    return ':'.join(mac_hex[i:i+2] for i in range(0, 12, 2)).upper()
            return str(mac_bytes)
        except Exception:
            return ''
    
    def close(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)

# Example usage
async def main():
    """Example SNMP monitoring."""
    manager = SNMPManager()
    
    # Create SNMP device
    device = SNMPDevice(
        ip_address="192.168.1.1",
        community="public",
        version=2
    )
    
    try:
        # Get system information
        system_info = await manager.get_system_info(device)
        if system_info:
            print(f"Device: {system_info.hostname}")
            print(f"Description: {system_info.description}")
            print(f"Uptime: {system_info.uptime} seconds")
        
        # Get CPU usage
        cpu_usage = await manager.get_cpu_usage(device)
        if cpu_usage:
            print(f"CPU Usage: {cpu_usage}%")
        
        # Get memory usage
        memory_usage = await manager.get_memory_usage(device)
        if memory_usage:
            print(f"Memory Usage: {memory_usage['usage_percent']}%")
        
        # Get interfaces
        interfaces = await manager.get_interfaces(device)
        print(f"Found {len(interfaces)} interfaces:")
        for interface in interfaces[:3]:  # Show first 3
            print(f"  {interface.name}: {interface.description}")
            print(f"    Status: {'UP' if interface.oper_status == 1 else 'DOWN'}")
            print(f"    Speed: {interface.speed} bps")
    
    finally:
        manager.close()

if __name__ == "__main__":
    asyncio.run(main())
