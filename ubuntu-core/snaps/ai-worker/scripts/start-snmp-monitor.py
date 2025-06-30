#!/usr/bin/env python3
"""
Start SNMP monitoring service for AI worker node
"""

import os
import sys
import asyncio
import logging
import signal
import json
from pathlib import Path

# Add the src directory to Python path
snap_path = os.environ.get('SNAP', '')
if snap_path:
    sys.path.insert(0, os.path.join(snap_path, 'lib/ai-worker'))

from snmp_monitor import SNMPMonitor, SNMPTarget
from snmp_agent import SNMPAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SNMPService:
    """Combined SNMP agent and monitor service"""
    
    def __init__(self):
        self.config = self._load_config()
        self._shutdown = False
        
        # Get node ID
        self.node_id = self.config.get('NODE_ID', os.uname().nodename)
        
        # Management server URL
        self.management_url = self.config.get(
            'MANAGEMENT_SERVER_URL',
            os.environ.get('MANAGEMENT_SERVER_URL', 'http://localhost:8000')
        )
        
        # Initialize components based on configuration
        self.agent = None
        self.monitor = None
        
        if self.config.get('ENABLE_SNMP_AGENT', True):
            self.agent = SNMPAgent(
                port=self.config.get('SNMP_AGENT_PORT', 161),
                community=self.config.get('SNMP_COMMUNITY', 'public')
            )
            
        if self.config.get('ENABLE_SNMP_MONITOR', True):
            self.monitor = SNMPMonitor(
                management_url=self.management_url,
                node_id=self.node_id
            )
            
    def _load_config(self) -> dict:
        """Load configuration from file and environment"""
        config = {
            'ENABLE_SNMP_AGENT': True,
            'ENABLE_SNMP_MONITOR': True,
            'SNMP_AGENT_PORT': 161,
            'SNMP_COMMUNITY': 'public',
        }
        
        # Load from config file
        config_file = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current')) / 'snmp-config.json'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                
        # Override with environment variables
        for key in config:
            env_key = f"SNMP_{key}"
            if env_key in os.environ:
                value = os.environ[env_key]
                # Convert boolean strings
                if value.lower() in ('true', 'false'):
                    config[key] = value.lower() == 'true'
                # Convert numeric strings
                elif value.isdigit():
                    config[key] = int(value)
                else:
                    config[key] = value
                    
        # Additional environment variables
        if 'NODE_ID' in os.environ:
            config['NODE_ID'] = os.environ['NODE_ID']
        if 'MANAGEMENT_SERVER_URL' in os.environ:
            config['MANAGEMENT_SERVER_URL'] = os.environ['MANAGEMENT_SERVER_URL']
            
        return config
        
    async def start(self):
        """Start SNMP services"""
        logger.info("Starting SNMP services...")
        logger.info(f"Node ID: {self.node_id}")
        logger.info(f"Management URL: {self.management_url}")
        
        tasks = []
        
        # Start SNMP agent
        if self.agent:
            logger.info(f"Starting SNMP agent on port {self.config['SNMP_AGENT_PORT']}")
            # Note: SNMP agent needs to run in a separate thread due to pysnmp design
            agent_task = asyncio.create_task(self._run_agent())
            tasks.append(agent_task)
            
        # Start SNMP monitor
        if self.monitor:
            logger.info("Starting SNMP monitor")
            await self.monitor.start()
            
            # Load monitoring targets
            await self._load_monitoring_targets()
            
        # Main loop
        try:
            while not self._shutdown:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in SNMP service: {e}")
            
        finally:
            # Cleanup
            if tasks:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                
    async def _run_agent(self):
        """Run SNMP agent"""
        try:
            await self.agent.start()
        except Exception as e:
            logger.error(f"SNMP agent error: {e}")
            
    async def _load_monitoring_targets(self):
        """Load SNMP monitoring targets"""
        # Check for targets file
        targets_file = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current')) / 'snmp-targets.json'
        
        if targets_file.exists():
            try:
                with open(targets_file) as f:
                    targets_data = json.load(f)
                    
                for target_data in targets_data:
                    target = SNMPTarget(**target_data)
                    await self.monitor.add_target(target)
                    
                logger.info(f"Loaded {len(targets_data)} SNMP monitoring targets")
                
            except Exception as e:
                logger.error(f"Failed to load SNMP targets: {e}")
        else:
            # Create example targets file
            example_targets = [
                {
                    "device_id": "router-1",
                    "hostname": "192.168.1.1",
                    "community": "public",
                    "interval": 300
                },
                {
                    "device_id": "switch-1",
                    "hostname": "192.168.1.2",
                    "community": "public",
                    "interval": 300
                }
            ]
            
            try:
                with open(targets_file, 'w') as f:
                    json.dump(example_targets, f, indent=2)
                logger.info(f"Created example SNMP targets file: {targets_file}")
            except Exception as e:
                logger.error(f"Failed to create example targets file: {e}")
                
    async def shutdown(self):
        """Shutdown SNMP services"""
        logger.info("Shutting down SNMP services...")
        self._shutdown = True
        
        if self.monitor:
            await self.monitor.stop()
            
        if self.agent:
            await self.agent.stop()
            
        logger.info("SNMP services stopped")
        
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self._shutdown = True


async def main():
    """Main entry point"""
    service = SNMPService()
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, service.handle_signal)
    signal.signal(signal.SIGINT, service.handle_signal)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await service.shutdown()


if __name__ == "__main__":
    # Check if running as root (required for port 161)
    if os.geteuid() != 0 and os.environ.get('SNMP_AGENT_PORT', '161') == '161':
        logger.warning("SNMP agent requires root privileges for port 161")
        logger.warning("Consider using a non-privileged port (>1024) or running with sudo")
        
    asyncio.run(main())