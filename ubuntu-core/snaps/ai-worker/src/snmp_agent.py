#!/usr/bin/env python3
"""
SNMP Agent for AI Worker Node
Provides SNMP monitoring capabilities for the worker node
"""

import os
import asyncio
import logging
import socket
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import psutil
import platform
from pysnmp.hlapi.asyncio import *
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.proto import rfc1902
from pysnmp.smi import builder, view, error

logger = logging.getLogger(__name__)


class SNMPAgent:
    """SNMP Agent for AI Worker monitoring"""
    
    def __init__(self, port: int = 161, community: str = 'public'):
        self.port = port
        self.community = community
        self.snmp_engine = None
        self.transport_dispatcher = None
        
        # OID base for custom MIB
        self.oid_base = '1.3.6.1.4.1.99999'  # Private enterprise number
        
        # System information cache
        self.system_info = self._get_system_info()
        
        # Metrics update interval
        self.update_interval = 60  # seconds
        self.last_update = datetime.utcnow()
        self.metrics_cache = {}
        
    def _get_system_info(self) -> Dict[str, str]:
        """Get static system information"""
        return {
            'sysDescr': f"AI Worker Node - {platform.platform()}",
            'sysObjectID': f"{self.oid_base}.1",
            'sysUpTime': '0',  # Will be calculated dynamically
            'sysContact': os.environ.get('SNMP_CONTACT', 'admin@ai-worker'),
            'sysName': socket.gethostname(),
            'sysLocation': os.environ.get('SNMP_LOCATION', 'AI Cluster'),
            'sysServices': '72',  # Layer 3 + applications
        }
        
    async def start(self):
        """Start the SNMP agent"""
        try:
            # Create SNMP engine
            self.snmp_engine = engine.SnmpEngine()
            
            # Configure transport
            config.addTransport(
                self.snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode(('0.0.0.0', self.port))
            )
            
            # Configure SNMPv2c community
            config.addV1System(self.snmp_engine, 'read-community', self.community)
            
            # Configure vacm (View-based Access Control Model)
            config.addVacmUser(self.snmp_engine, 2, 'read-community', 'noAuthNoPriv',
                             readSubTree=(1, 3, 6, 1, 2, 1))
            config.addVacmUser(self.snmp_engine, 2, 'read-community', 'noAuthNoPriv',
                             readSubTree=self._oid_to_tuple(self.oid_base))
            
            # Create and configure MIB controller
            mib_builder = self.snmp_engine.msgAndPduDsp.mibInstrumController.mibBuilder
            
            # Register command responder
            cmdrsp.GetCommandResponder(self.snmp_engine, self._handle_get_request)
            cmdrsp.NextCommandResponder(self.snmp_engine, self._handle_next_request)
            cmdrsp.BulkCommandResponder(self.snmp_engine, self._handle_bulk_request)
            
            # Start metrics update task
            asyncio.create_task(self._update_metrics_loop())
            
            logger.info(f"SNMP agent started on port {self.port}")
            
            # Run the agent
            self.transport_dispatcher = self.snmp_engine.transportDispatcher
            self.transport_dispatcher.jobStarted(1)
            
            try:
                await self.transport_dispatcher.runDispatcher()
            except Exception:
                raise
                
        except Exception as e:
            logger.error(f"Failed to start SNMP agent: {e}")
            raise
            
    async def stop(self):
        """Stop the SNMP agent"""
        if self.transport_dispatcher:
            self.transport_dispatcher.jobFinished(1)
        if self.snmp_engine:
            self.snmp_engine.transportDispatcher.closeDispatcher()
        logger.info("SNMP agent stopped")
        
    def _oid_to_tuple(self, oid_str: str) -> Tuple[int, ...]:
        """Convert OID string to tuple"""
        return tuple(int(x) for x in oid_str.split('.'))
        
    async def _update_metrics_loop(self):
        """Periodically update metrics cache"""
        while True:
            try:
                await self._update_metrics()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                await asyncio.sleep(self.update_interval)
                
    async def _update_metrics(self):
        """Update cached metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network interfaces
            net_io = psutil.net_io_counters(pernic=True)
            
            # Process metrics
            process = psutil.Process()
            
            # GPU metrics (if available)
            gpu_metrics = await self._get_gpu_metrics()
            
            # Update cache
            self.metrics_cache = {
                # Standard MIB-2 system group
                '1.3.6.1.2.1.1.1.0': self.system_info['sysDescr'],
                '1.3.6.1.2.1.1.2.0': self.system_info['sysObjectID'],
                '1.3.6.1.2.1.1.3.0': self._get_uptime_ticks(),
                '1.3.6.1.2.1.1.4.0': self.system_info['sysContact'],
                '1.3.6.1.2.1.1.5.0': self.system_info['sysName'],
                '1.3.6.1.2.1.1.6.0': self.system_info['sysLocation'],
                '1.3.6.1.2.1.1.7.0': int(self.system_info['sysServices']),
                
                # Host resources MIB
                '1.3.6.1.2.1.25.1.1.0': self._get_uptime_ticks(),  # hrSystemUptime
                '1.3.6.1.2.1.25.2.2.0': int(memory.total / 1024),  # hrMemorySize (KB)
                
                # Custom AI Worker MIB
                f'{self.oid_base}.2.1.0': int(cpu_percent),  # CPU usage percent
                f'{self.oid_base}.2.2.0': int(memory.percent),  # Memory usage percent
                f'{self.oid_base}.2.3.0': int(memory.used),  # Memory used bytes
                f'{self.oid_base}.2.4.0': int(memory.available),  # Memory available bytes
                f'{self.oid_base}.2.5.0': int(disk.percent),  # Disk usage percent
                f'{self.oid_base}.2.6.0': int(disk.used),  # Disk used bytes
                f'{self.oid_base}.2.7.0': int(disk.free),  # Disk free bytes
                
                # Ray worker status
                f'{self.oid_base}.3.1.0': self._get_ray_status(),  # Ray worker status
                f'{self.oid_base}.3.2.0': self._get_ray_tasks_completed(),  # Tasks completed
                f'{self.oid_base}.3.3.0': self._get_ray_cpu_allocated(),  # CPUs allocated
                f'{self.oid_base}.3.4.0': self._get_ray_memory_allocated(),  # Memory allocated
                
                # GPU metrics
                f'{self.oid_base}.4.1.0': gpu_metrics.get('count', 0),  # GPU count
                f'{self.oid_base}.4.2.0': gpu_metrics.get('utilization', 0),  # GPU utilization
                f'{self.oid_base}.4.3.0': gpu_metrics.get('memory_used', 0),  # GPU memory used
                f'{self.oid_base}.4.4.0': gpu_metrics.get('temperature', 0),  # GPU temperature
            }
            
            # Add network interface metrics
            if_index = 1
            for if_name, stats in net_io.items():
                base_oid = f'{self.oid_base}.5.{if_index}'
                self.metrics_cache.update({
                    f'{base_oid}.1.0': if_name,  # Interface name
                    f'{base_oid}.2.0': int(stats.bytes_sent),  # Bytes sent
                    f'{base_oid}.3.0': int(stats.bytes_recv),  # Bytes received
                    f'{base_oid}.4.0': int(stats.packets_sent),  # Packets sent
                    f'{base_oid}.5.0': int(stats.packets_recv),  # Packets received
                })
                if_index += 1
                
            self.last_update = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            
    def _get_uptime_ticks(self) -> int:
        """Get system uptime in hundredths of a second"""
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        return int(uptime.total_seconds() * 100)
        
    def _get_ray_status(self) -> int:
        """Get Ray worker status (0=stopped, 1=running, 2=error)"""
        try:
            import ray
            if ray.is_initialized():
                return 1
            return 0
        except:
            return 0
            
    def _get_ray_tasks_completed(self) -> int:
        """Get number of Ray tasks completed"""
        # This would be retrieved from Ray metrics
        return 0
        
    def _get_ray_cpu_allocated(self) -> int:
        """Get Ray CPU allocation"""
        try:
            import ray
            if ray.is_initialized():
                resources = ray.available_resources()
                return int(resources.get('CPU', 0))
            return 0
        except:
            return 0
            
    def _get_ray_memory_allocated(self) -> int:
        """Get Ray memory allocation in bytes"""
        try:
            import ray
            if ray.is_initialized():
                resources = ray.available_resources()
                # Ray reports memory in bytes
                return int(resources.get('memory', 0))
            return 0
        except:
            return 0
            
    async def _get_gpu_metrics(self) -> Dict[str, int]:
        """Get GPU metrics if available"""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=count,utilization.gpu,memory.used,temperature.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                values = result.stdout.strip().split(',')
                return {
                    'count': int(values[0]) if len(values) > 0 else 0,
                    'utilization': int(values[1]) if len(values) > 1 else 0,
                    'memory_used': int(values[2]) if len(values) > 2 else 0,
                    'temperature': int(values[3]) if len(values) > 3 else 0,
                }
        except:
            pass
            
        return {'count': 0, 'utilization': 0, 'memory_used': 0, 'temperature': 0}
        
    def _handle_get_request(self, snmpEngine, stateReference, contextName,
                           varBinds, acInfo):
        """Handle SNMP GET requests"""
        rspVarBinds = []
        
        for oid, val in varBinds:
            oid_str = '.'.join(str(x) for x in oid)
            
            if oid_str in self.metrics_cache:
                value = self.metrics_cache[oid_str]
                
                # Convert to appropriate SNMP type
                if isinstance(value, str):
                    rspVarBinds.append((oid, rfc1902.OctetString(value)))
                elif isinstance(value, int):
                    rspVarBinds.append((oid, rfc1902.Integer(value)))
                else:
                    rspVarBinds.append((oid, rfc1902.OctetString(str(value))))
            else:
                # No such object
                rspVarBinds.append((oid, val))
                
        return rspVarBinds
        
    def _handle_next_request(self, snmpEngine, stateReference, contextName,
                            varBinds, acInfo):
        """Handle SNMP GETNEXT requests"""
        rspVarBinds = []
        
        for oid, val in varBinds:
            oid_str = '.'.join(str(x) for x in oid)
            
            # Find next OID
            next_oid = self._find_next_oid(oid_str)
            if next_oid:
                value = self.metrics_cache[next_oid]
                oid_tuple = self._oid_to_tuple(next_oid)
                
                if isinstance(value, str):
                    rspVarBinds.append((oid_tuple, rfc1902.OctetString(value)))
                elif isinstance(value, int):
                    rspVarBinds.append((oid_tuple, rfc1902.Integer(value)))
                else:
                    rspVarBinds.append((oid_tuple, rfc1902.OctetString(str(value))))
            else:
                # End of MIB
                rspVarBinds.append((oid, val))
                
        return rspVarBinds
        
    def _handle_bulk_request(self, snmpEngine, stateReference, contextName,
                            nonRepeaters, maxRepetitions, varBinds, acInfo):
        """Handle SNMP GETBULK requests"""
        # For simplicity, treat as multiple GETNEXT
        rspVarBinds = []
        
        # Handle non-repeaters
        for i in range(min(nonRepeaters, len(varBinds))):
            rspVarBinds.extend(
                self._handle_next_request(snmpEngine, stateReference, contextName,
                                        [varBinds[i]], acInfo)
            )
            
        # Handle repeaters
        for i in range(nonRepeaters, len(varBinds)):
            oid, val = varBinds[i]
            for j in range(maxRepetitions):
                next_result = self._handle_next_request(
                    snmpEngine, stateReference, contextName,
                    [(oid, val)], acInfo
                )
                if next_result:
                    rspVarBinds.extend(next_result)
                    oid = next_result[0][0]  # Use for next iteration
                else:
                    break
                    
        return rspVarBinds
        
    def _find_next_oid(self, oid_str: str) -> Optional[str]:
        """Find the next OID in lexicographic order"""
        sorted_oids = sorted(self.metrics_cache.keys())
        
        for i, oid in enumerate(sorted_oids):
            if self._oid_compare(oid, oid_str) > 0:
                return oid
                
        return None
        
    def _oid_compare(self, oid1: str, oid2: str) -> int:
        """Compare two OIDs lexicographically"""
        parts1 = [int(x) for x in oid1.split('.')]
        parts2 = [int(x) for x in oid2.split('.')]
        
        for i in range(min(len(parts1), len(parts2))):
            if parts1[i] < parts2[i]:
                return -1
            elif parts1[i] > parts2[i]:
                return 1
                
        # If all compared parts are equal, shorter OID comes first
        return len(parts1) - len(parts2)


async def main():
    """Test SNMP agent"""
    logging.basicConfig(level=logging.INFO)
    
    agent = SNMPAgent(port=1161)  # Non-privileged port for testing
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())