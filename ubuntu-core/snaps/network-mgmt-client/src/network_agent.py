#!/usr/bin/env python3
"""
Network Management Client Agent for Ubuntu Core
Main service that coordinates all network management functions
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/snap/network-mgmt-client/current/network-agent.log')
    ]
)
logger = logging.getLogger(__name__)

class NetworkAgent:
    """Main network management agent for Ubuntu Core devices"""
    
    def __init__(self):
        self.config = self._load_config()
        self.running = False
        self.services = {}
        self.status = {
            'agent_id': self._get_agent_id(),
            'hostname': os.uname().nodename,
            'platform': 'ubuntu-core-24',
            'version': '1.0.0',
            'started_at': None,
            'last_heartbeat': None,
            'services': {}
        }
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from snap data"""
        config_path = Path(os.environ.get('SNAP_DATA', '/var/snap/network-mgmt-client/current')) / 'config.json'
        
        default_config = {
            'server_endpoint': os.environ.get('NETWORK_MGMT_SERVER', 'https://mgmt.local:8000'),
            'heartbeat_interval': 30,
            'log_level': 'INFO',
            'enable_backup': True,
            'enable_ray': True,
            'enable_snmp': True,
            'enable_ssh_management': True,
            'hardware_monitoring_interval': 60,
            'network_scan_interval': 300,
            'api_port': 8080,
            'ssl_verify': True,
            'ray_address': None,  # Auto-discover or set manually
        }
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    return {**default_config, **config}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
            
        return default_config
    
    def _get_agent_id(self) -> str:
        """Get unique agent ID for this device"""
        agent_id_path = Path(os.environ.get('SNAP_DATA', '/var/snap/network-mgmt-client/current')) / 'agent_id'
        
        try:
            if agent_id_path.exists():
                return agent_id_path.read_text().strip()
        except Exception:
            pass
            
        # Generate new agent ID
        import uuid
        agent_id = str(uuid.uuid4())
        
        try:
            agent_id_path.write_text(agent_id)
        except Exception as e:
            logger.warning(f"Failed to save agent ID: {e}")
            
        return agent_id
    
    async def start(self):
        """Start the network management agent"""
        logger.info("Starting Network Management Agent")
        self.running = True
        self.status['started_at'] = datetime.utcnow().isoformat()
        
        try:
            # Start all services
            await self._start_services()
            
            # Start main loop
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Agent failed: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop the network management agent"""
        logger.info("Stopping Network Management Agent")
        self.running = False
        
        # Stop all services
        await self._stop_services()
        
        logger.info("Network Management Agent stopped")
    
    async def _start_services(self):
        """Start all configured services"""
        # Hardware monitoring service
        if self.config.get('enable_hardware_monitoring', True):
            await self._start_hardware_monitor()
        
        # Network monitoring service
        if self.config.get('enable_network_monitoring', True):
            await self._start_network_monitor()
        
        # SSH management service
        if self.config.get('enable_ssh_management', True):
            await self._start_ssh_manager()
        
        # SNMP monitoring service
        if self.config.get('enable_snmp', True):
            await self._start_snmp_monitor()
        
        # Backup service
        if self.config.get('enable_backup', True):
            await self._start_backup_service()
        
        # Ray worker service
        if self.config.get('enable_ray', True):
            await self._start_ray_worker()
        
        # API service
        await self._start_api_service()
        
        logger.info(f"Started {len(self.services)} services")
    
    async def _stop_services(self):
        """Stop all services"""
        for service_name, service_task in self.services.items():
            try:
                logger.info(f"Stopping {service_name}")
                service_task.cancel()
                await service_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error stopping {service_name}: {e}")
        
        self.services.clear()
    
    async def _start_hardware_monitor(self):
        """Start hardware monitoring service"""
        logger.info("Starting hardware monitor")
        self.services['hardware_monitor'] = asyncio.create_task(
            self._hardware_monitor_loop()
        )
        self.status['services']['hardware_monitor'] = 'running'
    
    async def _hardware_monitor_loop(self):
        """Hardware monitoring loop"""
        import psutil
        
        while self.running:
            try:
                # Collect hardware metrics
                metrics = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'cpu': {
                        'percent': psutil.cpu_percent(interval=1),
                        'count': psutil.cpu_count(),
                        'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                    },
                    'memory': psutil.virtual_memory()._asdict(),
                    'disk': [disk._asdict() for disk in psutil.disk_usage('/')],
                    'network': psutil.net_io_counters()._asdict(),
                    'boot_time': psutil.boot_time(),
                    'load_avg': os.getloadavg()
                }
                
                # Store metrics
                await self._store_metrics('hardware', metrics)
                
                # Send to server if configured
                await self._send_metrics('hardware', metrics)
                
                await asyncio.sleep(self.config['hardware_monitoring_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Hardware monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _start_network_monitor(self):
        """Start network monitoring service"""
        logger.info("Starting network monitor")
        self.services['network_monitor'] = asyncio.create_task(
            self._network_monitor_loop()
        )
        self.status['services']['network_monitor'] = 'running'
    
    async def _network_monitor_loop(self):
        """Network monitoring loop"""
        while self.running:
            try:
                # Network interface monitoring
                import psutil
                
                interfaces = {}
                for interface, addrs in psutil.net_if_addrs().items():
                    interfaces[interface] = {
                        'addresses': [addr._asdict() for addr in addrs],
                        'stats': psutil.net_if_stats()[interface]._asdict() if interface in psutil.net_if_stats() else None
                    }
                
                metrics = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'interfaces': interfaces,
                    'connections': len(psutil.net_connections()),
                    'io_counters': psutil.net_io_counters()._asdict()
                }
                
                await self._store_metrics('network', metrics)
                await self._send_metrics('network', metrics)
                
                await asyncio.sleep(self.config['network_scan_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Network monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _start_ssh_manager(self):
        """Start SSH management service"""
        logger.info("Starting SSH manager")
        self.services['ssh_manager'] = asyncio.create_task(
            self._ssh_manager_loop()
        )
        self.status['services']['ssh_manager'] = 'running'
    
    async def _ssh_manager_loop(self):
        """SSH management loop"""
        while self.running:
            try:
                # Monitor SSH connections and manage authorized keys
                # This would integrate with the main platform's SSH management
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSH manager error: {e}")
                await asyncio.sleep(60)
    
    async def _start_snmp_monitor(self):
        """Start SNMP monitoring service"""
        logger.info("Starting SNMP monitor")
        self.services['snmp_monitor'] = asyncio.create_task(
            self._snmp_monitor_loop()
        )
        self.status['services']['snmp_monitor'] = 'running'
    
    async def _snmp_monitor_loop(self):
        """SNMP monitoring loop"""
        while self.running:
            try:
                # SNMP monitoring logic
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SNMP monitor error: {e}")
                await asyncio.sleep(60)
    
    async def _start_backup_service(self):
        """Start backup service"""
        logger.info("Starting backup service")
        self.services['backup_service'] = asyncio.create_task(
            self._backup_service_loop()
        )
        self.status['services']['backup_service'] = 'running'
    
    async def _backup_service_loop(self):
        """Backup service loop"""
        while self.running:
            try:
                # Local backup and sync logic
                await asyncio.sleep(3600)  # Check every hour
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup service error: {e}")
                await asyncio.sleep(300)
    
    async def _start_ray_worker(self):
        """Start Ray worker service"""
        if not self.config.get('enable_ray', True):
            return
            
        logger.info("Starting Ray worker")
        self.services['ray_worker'] = asyncio.create_task(
            self._ray_worker_loop()
        )
        self.status['services']['ray_worker'] = 'running'
    
    async def _ray_worker_loop(self):
        """Ray worker loop"""
        while self.running:
            try:
                # Ray worker management
                # This would connect to the Ray head node
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ray worker error: {e}")
                await asyncio.sleep(60)
    
    async def _start_api_service(self):
        """Start local API service"""
        logger.info("Starting API service")
        self.services['api_service'] = asyncio.create_task(
            self._api_service_loop()
        )
        self.status['services']['api_service'] = 'running'
    
    async def _api_service_loop(self):
        """API service loop"""
        while self.running:
            try:
                # Simple HTTP API for local management
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"API service error: {e}")
                await asyncio.sleep(60)
    
    async def _main_loop(self):
        """Main agent loop"""
        while self.running:
            try:
                # Update heartbeat
                self.status['last_heartbeat'] = datetime.utcnow().isoformat()
                
                # Send heartbeat to server
                await self._send_heartbeat()
                
                # Check service health
                await self._check_service_health()
                
                await asyncio.sleep(self.config['heartbeat_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(30)
    
    async def _send_heartbeat(self):
        """Send heartbeat to management server"""
        try:
            # This would send status to the management server
            logger.debug(f"Heartbeat: {self.status['agent_id']}")
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")
    
    async def _check_service_health(self):
        """Check health of all services"""
        for service_name, service_task in self.services.items():
            if service_task.done():
                logger.warning(f"Service {service_name} has stopped")
                self.status['services'][service_name] = 'stopped'
                # Could restart service here
    
    async def _store_metrics(self, metric_type: str, data: Dict[str, Any]):
        """Store metrics locally"""
        try:
            metrics_dir = Path(os.environ.get('SNAP_DATA', '/var/snap/network-mgmt-client/current')) / 'metrics'
            metrics_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H')
            metrics_file = metrics_dir / f"{metric_type}_{timestamp}.json"
            
            # Append to hourly file
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
                
        except Exception as e:
            logger.warning(f"Failed to store metrics: {e}")
    
    async def _send_metrics(self, metric_type: str, data: Dict[str, Any]):
        """Send metrics to management server"""
        try:
            # This would send metrics to the server
            pass
        except Exception as e:
            logger.warning(f"Failed to send metrics: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    global agent
    if agent:
        asyncio.create_task(agent.stop())

async def main():
    """Main entry point"""
    global agent
    agent = NetworkAgent()
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await agent.stop()

if __name__ == '__main__':
    asyncio.run(main())