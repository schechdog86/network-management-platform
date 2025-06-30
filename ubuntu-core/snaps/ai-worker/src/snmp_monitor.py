#!/usr/bin/env python3
"""
SNMP Monitor for AI Worker Node
Monitors other SNMP-enabled devices and reports to management platform
"""

import os
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import aiohttp
from pysnmp.hlapi.asyncio import *

logger = logging.getLogger(__name__)


@dataclass
class SNMPTarget:
    """SNMP monitoring target"""
    device_id: str
    hostname: str
    port: int = 161
    community: str = 'public'
    version: int = 2
    timeout: int = 5
    retry_count: int = 3
    interval: int = 300  # seconds


class SNMPMonitor:
    """SNMP monitor for AI worker node"""
    
    # Common OIDs for monitoring
    OIDS = {
        # System MIB
        'sysDescr': '1.3.6.1.2.1.1.1.0',
        'sysObjectID': '1.3.6.1.2.1.1.2.0',
        'sysUpTime': '1.3.6.1.2.1.1.3.0',
        'sysContact': '1.3.6.1.2.1.1.4.0',
        'sysName': '1.3.6.1.2.1.1.5.0',
        'sysLocation': '1.3.6.1.2.1.1.6.0',
        
        # Host Resources MIB
        'hrSystemUptime': '1.3.6.1.2.1.25.1.1.0',
        'hrSystemNumUsers': '1.3.6.1.2.1.25.1.5.0',
        'hrSystemProcesses': '1.3.6.1.2.1.25.1.6.0',
        'hrMemorySize': '1.3.6.1.2.1.25.2.2.0',
        
        # IF-MIB (interfaces)
        'ifNumber': '1.3.6.1.2.1.2.1.0',
        
        # UCD-SNMP-MIB (net-snmp)
        'memTotalReal': '1.3.6.1.4.1.2021.4.5.0',
        'memAvailReal': '1.3.6.1.4.1.2021.4.6.0',
        'memTotalSwap': '1.3.6.1.4.1.2021.4.3.0',
        'memAvailSwap': '1.3.6.1.4.1.2021.4.4.0',
        'ssCpuUser': '1.3.6.1.4.1.2021.11.9.0',
        'ssCpuSystem': '1.3.6.1.4.1.2021.11.10.0',
        'ssCpuIdle': '1.3.6.1.4.1.2021.11.11.0',
        'load1min': '1.3.6.1.4.1.2021.10.1.3.1',
        'load5min': '1.3.6.1.4.1.2021.10.1.3.2',
        'load15min': '1.3.6.1.4.1.2021.10.1.3.3',
    }
    
    def __init__(self, management_url: str, node_id: str):
        self.management_url = management_url
        self.node_id = node_id
        self.targets: Dict[str, SNMPTarget] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        """Start SNMP monitor"""
        self.session = aiohttp.ClientSession()
        logger.info("SNMP monitor started")
        
        # Load targets from configuration
        await self._load_targets()
        
    async def stop(self):
        """Stop SNMP monitor"""
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
            
        # Wait for tasks to complete
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
            
        # Close session
        if self.session:
            await self.session.close()
            
        logger.info("SNMP monitor stopped")
        
    async def add_target(self, target: SNMPTarget):
        """Add a monitoring target"""
        if target.device_id in self.targets:
            await self.remove_target(target.device_id)
            
        self.targets[target.device_id] = target
        
        # Start monitoring task
        self.monitoring_tasks[target.device_id] = asyncio.create_task(
            self._monitor_target(target)
        )
        
        logger.info(f"Added SNMP target: {target.device_id} ({target.hostname})")
        
    async def remove_target(self, device_id: str):
        """Remove a monitoring target"""
        if device_id in self.monitoring_tasks:
            self.monitoring_tasks[device_id].cancel()
            try:
                await self.monitoring_tasks[device_id]
            except asyncio.CancelledError:
                pass
            del self.monitoring_tasks[device_id]
            
        if device_id in self.targets:
            del self.targets[device_id]
            logger.info(f"Removed SNMP target: {device_id}")
            
    async def _load_targets(self):
        """Load monitoring targets from configuration"""
        config_file = os.path.join(
            os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current'),
            'snmp-targets.json'
        )
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    targets_data = json.load(f)
                    
                for target_data in targets_data:
                    target = SNMPTarget(**target_data)
                    await self.add_target(target)
                    
            except Exception as e:
                logger.error(f"Failed to load SNMP targets: {e}")
                
    async def _monitor_target(self, target: SNMPTarget):
        """Monitor a single SNMP target"""
        while True:
            try:
                # Collect SNMP data
                metrics = await self._collect_snmp_data(target)
                
                if metrics:
                    # Send to management platform
                    await self._send_metrics(target.device_id, metrics)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring {target.device_id}: {e}")
                
                # Report error
                await self._send_error(target.device_id, str(e))
                
            # Wait for next interval
            await asyncio.sleep(target.interval)
            
    async def _collect_snmp_data(self, target: SNMPTarget) -> Dict[str, Any]:
        """Collect SNMP data from target"""
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'node_id': self.node_id,
            'device_id': target.device_id,
            'hostname': target.hostname,
        }
        
        try:
            # Get system information
            system_oids = ['sysDescr', 'sysName', 'sysUpTime', 'sysLocation']
            system_data = await self._get_snmp_values(target, system_oids)
            metrics['system'] = system_data
            
            # Get CPU metrics
            cpu_oids = ['ssCpuUser', 'ssCpuSystem', 'ssCpuIdle', 
                       'load1min', 'load5min', 'load15min']
            cpu_data = await self._get_snmp_values(target, cpu_oids)
            
            # Calculate CPU usage
            if all(k in cpu_data for k in ['ssCpuUser', 'ssCpuSystem', 'ssCpuIdle']):
                total = (cpu_data['ssCpuUser'] + cpu_data['ssCpuSystem'] + 
                        cpu_data['ssCpuIdle'])
                if total > 0:
                    cpu_data['usage_percent'] = 100 - (cpu_data['ssCpuIdle'] / total * 100)
                    
            metrics['cpu'] = cpu_data
            
            # Get memory metrics
            memory_oids = ['hrMemorySize', 'memTotalReal', 'memAvailReal',
                          'memTotalSwap', 'memAvailSwap']
            memory_data = await self._get_snmp_values(target, memory_oids)
            
            # Calculate memory usage
            if 'memTotalReal' in memory_data and 'memAvailReal' in memory_data:
                total = memory_data['memTotalReal']
                available = memory_data['memAvailReal']
                if total > 0:
                    memory_data['usage_percent'] = ((total - available) / total) * 100
                    memory_data['used_kb'] = total - available
                    
            metrics['memory'] = memory_data
            
            # Get interface statistics
            interfaces = await self._get_interface_stats(target)
            metrics['interfaces'] = interfaces
            
            # Get disk usage (if available)
            disk_data = await self._get_disk_usage(target)
            if disk_data:
                metrics['disk'] = disk_data
                
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect SNMP data from {target.hostname}: {e}")
            raise
            
    async def _get_snmp_values(self, target: SNMPTarget, 
                              oid_names: List[str]) -> Dict[str, Any]:
        """Get multiple SNMP values"""
        result = {}
        
        # Build OID list
        oids = [ObjectType(ObjectIdentity(self.OIDS[name])) 
                for name in oid_names if name in self.OIDS]
        
        if not oids:
            return result
            
        # Perform SNMP GET
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            SnmpEngine(),
            CommunityData(target.community),
            UdpTransportTarget((target.hostname, target.port), 
                              timeout=target.timeout, retries=target.retry_count),
            ContextData(),
            *oids
        )
        
        if errorIndication:
            raise Exception(f"SNMP error: {errorIndication}")
        elif errorStatus:
            raise Exception(f"SNMP error: {errorStatus.prettyPrint()}")
            
        # Process results
        for varBind in varBinds:
            oid = str(varBind[0])
            value = varBind[1]
            
            # Find OID name
            for name, oid_str in self.OIDS.items():
                if oid == oid_str:
                    # Convert value to appropriate type
                    if isinstance(value, Integer):
                        result[name] = int(value)
                    elif isinstance(value, Counter32) or isinstance(value, Counter64):
                        result[name] = int(value)
                    elif isinstance(value, Gauge32):
                        result[name] = int(value)
                    elif isinstance(value, TimeTicks):
                        result[name] = int(value)
                    elif isinstance(value, OctetString):
                        result[name] = str(value)
                    else:
                        result[name] = str(value)
                    break
                    
        return result
        
    async def _get_interface_stats(self, target: SNMPTarget) -> List[Dict[str, Any]]:
        """Get network interface statistics"""
        interfaces = []
        
        # OIDs for interface data
        if_oids = {
            'name': '1.3.6.1.2.1.2.2.1.2',      # ifDescr
            'status': '1.3.6.1.2.1.2.2.1.8',    # ifOperStatus
            'in_octets': '1.3.6.1.2.1.2.2.1.10', # ifInOctets
            'out_octets': '1.3.6.1.2.1.2.2.1.16', # ifOutOctets
            'in_errors': '1.3.6.1.2.1.2.2.1.14', # ifInErrors
            'out_errors': '1.3.6.1.2.1.2.2.1.20', # ifOutErrors
        }
        
        try:
            # Get interface count
            count_result = await self._get_snmp_values(target, ['ifNumber'])
            if_count = count_result.get('ifNumber', 0)
            
            # Get data for each interface
            for if_index in range(1, min(if_count + 1, 50)):  # Limit to 50 interfaces
                interface_data = {'index': if_index}
                
                # Get interface attributes
                for attr, base_oid in if_oids.items():
                    oid = f"{base_oid}.{if_index}"
                    
                    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                        SnmpEngine(),
                        CommunityData(target.community),
                        UdpTransportTarget((target.hostname, target.port)),
                        ContextData(),
                        ObjectType(ObjectIdentity(oid))
                    )
                    
                    if not errorIndication and not errorStatus and varBinds:
                        value = varBinds[0][1]
                        
                        if isinstance(value, Integer):
                            interface_data[attr] = int(value)
                        elif isinstance(value, Counter32) or isinstance(value, Counter64):
                            interface_data[attr] = int(value)
                        elif isinstance(value, OctetString):
                            interface_data[attr] = str(value)
                        else:
                            interface_data[attr] = str(value)
                            
                # Only add interfaces with names
                if 'name' in interface_data:
                    interfaces.append(interface_data)
                    
        except Exception as e:
            logger.error(f"Failed to get interface stats: {e}")
            
        return interfaces
        
    async def _get_disk_usage(self, target: SNMPTarget) -> List[Dict[str, Any]]:
        """Get disk usage information"""
        disks = []
        
        # OIDs for disk data (UCD-SNMP-MIB)
        disk_oids = {
            'path': '1.3.6.1.4.1.2021.9.1.2',      # dskPath
            'total': '1.3.6.1.4.1.2021.9.1.6',     # dskTotal
            'available': '1.3.6.1.4.1.2021.9.1.7', # dskAvail
            'used': '1.3.6.1.4.1.2021.9.1.8',      # dskUsed
            'percent': '1.3.6.1.4.1.2021.9.1.9',   # dskPercent
        }
        
        try:
            # Try to get disk entries (up to 10)
            for disk_index in range(1, 11):
                disk_data = {'index': disk_index}
                
                for attr, base_oid in disk_oids.items():
                    oid = f"{base_oid}.{disk_index}"
                    
                    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                        SnmpEngine(),
                        CommunityData(target.community),
                        UdpTransportTarget((target.hostname, target.port)),
                        ContextData(),
                        ObjectType(ObjectIdentity(oid))
                    )
                    
                    if not errorIndication and not errorStatus and varBinds:
                        value = varBinds[0][1]
                        
                        if isinstance(value, Integer):
                            disk_data[attr] = int(value)
                        elif isinstance(value, OctetString):
                            disk_data[attr] = str(value)
                            
                # Only add valid disk entries
                if 'path' in disk_data and disk_data['path']:
                    disks.append(disk_data)
                else:
                    break  # No more disk entries
                    
        except Exception as e:
            logger.debug(f"Failed to get disk usage: {e}")
            
        return disks
        
    async def _send_metrics(self, device_id: str, metrics: Dict[str, Any]):
        """Send metrics to management platform"""
        if not self.session:
            return
            
        try:
            url = f"{self.management_url}/api/v1/snmp/metrics"
            headers = {'Content-Type': 'application/json'}
            
            async with self.session.post(url, json=metrics, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send metrics: {resp.status}")
                    
        except Exception as e:
            logger.error(f"Failed to send metrics to management platform: {e}")
            
    async def _send_error(self, device_id: str, error: str):
        """Send error notification to management platform"""
        if not self.session:
            return
            
        try:
            url = f"{self.management_url}/api/v1/snmp/error"
            data = {
                'device_id': device_id,
                'node_id': self.node_id,
                'error': error,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            async with self.session.post(url, json=data) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send error notification: {resp.status}")
                    
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")


async def main():
    """Test SNMP monitor"""
    logging.basicConfig(level=logging.INFO)
    
    monitor = SNMPMonitor(
        management_url="http://localhost:8000",
        node_id="test-node"
    )
    
    await monitor.start()
    
    # Add test target
    target = SNMPTarget(
        device_id="test-device",
        hostname="localhost",
        interval=30
    )
    await monitor.add_target(target)
    
    try:
        # Run for a while
        await asyncio.sleep(300)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())