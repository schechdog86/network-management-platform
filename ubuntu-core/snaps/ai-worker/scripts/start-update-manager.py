#!/usr/bin/env python3
"""
Start Update Manager service for AI worker node
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

from update_manager import AIWorkerUpdateManager, UpdatePolicy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UpdateManagerService:
    """Update Manager service wrapper"""
    
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
        
        # Initialize update manager
        self.update_manager = AIWorkerUpdateManager(
            management_url=self.management_url,
            node_id=self.node_id
        )
        
        # Override policy with environment configuration
        self._configure_update_policy()
        
    def _load_config(self) -> dict:
        """Load configuration from file and environment"""
        config = {}
        
        # Load from config file
        config_file = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current')) / 'update-config.json'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                
        # Override with environment variables
        env_vars = [
            'NODE_ID', 'MANAGEMENT_SERVER_URL', 'AUTO_UPDATE_ENABLED',
            'UPDATE_WINDOW_START', 'UPDATE_WINDOW_END', 'MAX_GPU_UTILIZATION',
            'MIN_IDLE_TIME', 'ENABLE_CANARY_UPDATES', 'ROLLBACK_ON_FAILURE',
            'UPDATE_CHECK_INTERVAL', 'DEFER_DURING_TRAINING'
        ]
        
        for var in env_vars:
            if var in os.environ:
                value = os.environ[var]
                # Convert boolean strings
                if value.lower() in ('true', 'false'):
                    config[var.lower()] = value.lower() == 'true'
                # Convert numeric strings
                elif value.replace('.', '').isdigit():
                    config[var.lower()] = float(value) if '.' in value else int(value)
                else:
                    config[var.lower()] = value
                    
        return config
        
    def _configure_update_policy(self):
        """Configure update policy from configuration"""
        policy = self.update_manager.policy
        
        # Map configuration to policy attributes
        config_mapping = {
            'auto_update_enabled': 'auto_update_enabled',
            'update_window_start': 'update_window_start',
            'update_window_end': 'update_window_end',
            'max_gpu_utilization': 'max_gpu_utilization',
            'min_idle_time': 'min_idle_time',
            'enable_canary_updates': 'enable_canary_updates',
            'rollback_on_failure': 'rollback_on_failure',
            'update_check_interval': 'update_check_interval',
            'defer_during_training': 'defer_during_training'
        }
        
        for config_key, policy_attr in config_mapping.items():
            if config_key in self.config:
                setattr(policy, policy_attr, self.config[config_key])
                logger.info(f"Set {policy_attr} = {self.config[config_key]}")
                
    async def start(self):
        """Start the update manager service"""
        logger.info("Starting Update Manager service...")
        logger.info(f"Node ID: {self.node_id}")
        logger.info(f"Management URL: {self.management_url}")
        logger.info(f"Auto updates: {self.update_manager.policy.auto_update_enabled}")
        logger.info(f"Update window: {self.update_manager.policy.update_window_start} - {self.update_manager.policy.update_window_end}")
        logger.info(f"Max GPU utilization: {self.update_manager.policy.max_gpu_utilization}%")
        
        try:
            # Create default configuration files
            await self._create_default_configs()
            
            # Start update manager
            await self.update_manager.start()
            
            # Main loop
            while not self._shutdown:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in update manager service: {e}")
            raise
            
        finally:
            await self.update_manager.stop()
            
    async def _create_default_configs(self):
        """Create default configuration files"""
        snap_data = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current'))
        
        # Create update policy file if it doesn't exist
        policy_file = snap_data / 'update-policy.json'
        if not policy_file.exists():
            default_policy = {
                "auto_update_enabled": True,
                "update_window_start": "02:00",
                "update_window_end": "06:00",
                "max_gpu_utilization": 10.0,
                "min_idle_time": 300,
                "enable_canary_updates": True,
                "rollback_on_failure": True,
                "update_check_interval": 3600,
                "defer_during_training": True
            }
            
            try:
                with open(policy_file, 'w') as f:
                    json.dump(default_policy, f, indent=2)
                logger.info(f"Created default update policy: {policy_file}")
            except Exception as e:
                logger.error(f"Failed to create update policy file: {e}")
                
        # Create update schedule file
        schedule_file = snap_data / 'update-schedule.json'
        if not schedule_file.exists():
            default_schedule = {
                "ai-worker": {
                    "channel": "stable",
                    "hold": False,
                    "priority": "high"
                },
                "ray-head": {
                    "channel": "stable", 
                    "hold": False,
                    "priority": "medium"
                },
                "network-manager-server": {
                    "channel": "stable",
                    "hold": False,
                    "priority": "low"
                }
            }
            
            try:
                with open(schedule_file, 'w') as f:
                    json.dump(default_schedule, f, indent=2)
                logger.info(f"Created default update schedule: {schedule_file}")
            except Exception as e:
                logger.error(f"Failed to create update schedule file: {e}")
                
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self._shutdown = True
        
    async def shutdown(self):
        """Shutdown the service"""
        logger.info("Shutting down Update Manager service...")
        self._shutdown = True
        await self.update_manager.stop()
        logger.info("Update Manager service stopped")


async def main():
    """Main entry point"""
    service = UpdateManagerService()
    
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
    # Check for required permissions
    if os.geteuid() != 0:
        logger.warning("Update manager may require elevated privileges for snap operations")
        logger.warning("Some operations may fail without proper permissions")
        
    asyncio.run(main())