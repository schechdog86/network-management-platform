#!/usr/bin/env python3
"""
Start SSH manager service for AI worker node
"""

import os
import sys
import asyncio
import logging
import signal
from pathlib import Path

# Add the src directory to Python path
snap_path = os.environ.get('SNAP', '')
if snap_path:
    sys.path.insert(0, os.path.join(snap_path, 'lib/ai-worker'))

from ssh_manager import SSHManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SSHManagerService:
    """SSH Manager service for AI worker"""
    
    def __init__(self):
        self.ssh_manager = SSHManager()
        self._shutdown = False
        
        # Configuration
        self.config = self._load_config()
        
        # Generate host key if needed
        self._ensure_host_key()
        
    def _load_config(self) -> dict:
        """Load configuration"""
        config = {
            'ENABLE_SSH': os.environ.get('ENABLE_SSH', 'true').lower() == 'true',
            'SSH_PORT': int(os.environ.get('SSH_PORT', '22')),
            'ALLOW_PASSWORD_AUTH': os.environ.get('ALLOW_PASSWORD_AUTH', 'false').lower() == 'true',
        }
        
        # Load from config file if exists
        config_file = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current')) / 'ssh-config.yaml'
        if config_file.exists():
            try:
                import yaml
                with open(config_file) as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        config.update(file_config)
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                
        return config
        
    def _ensure_host_key(self):
        """Ensure SSH host key exists"""
        try:
            # Check if host key exists
            if not self.ssh_manager.private_key_path.exists():
                logger.info("Generating SSH host key...")
                # Generate using the synchronous wrapper
                asyncio.get_event_loop().run_until_complete(
                    self.ssh_manager.generate_ssh_key(comment="ai-worker-host")
                )
                logger.info("SSH host key generated")
        except Exception as e:
            logger.error(f"Error ensuring host key: {e}")
            
    async def start(self):
        """Start the SSH manager service"""
        logger.info("Starting SSH manager service...")
        
        if not self.config['ENABLE_SSH']:
            logger.info("SSH is disabled in configuration")
            return
            
        try:
            # Display public key for user
            public_key = self.ssh_manager.get_public_key()
            if public_key:
                logger.info(f"SSH public key: {public_key[:50]}...")
                
                # Save public key to well-known location
                public_key_file = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current')) / 'ssh-host-key.pub'
                public_key_file.write_text(public_key)
                logger.info(f"Public key saved to: {public_key_file}")
                
            # List authorized keys periodically
            while not self._shutdown:
                authorized_keys = self.ssh_manager.list_authorized_keys()
                logger.info(f"Authorized keys count: {len(authorized_keys)}")
                
                # Check for new keys every 30 seconds
                await asyncio.sleep(30)
                
        except Exception as e:
            logger.error(f"Error in SSH manager service: {e}")
            raise
            
    async def add_management_key(self, public_key: str):
        """Add management platform's public key"""
        try:
            self.ssh_manager.add_authorized_key(
                public_key,
                comment="network-management-platform"
            )
            logger.info("Added management platform SSH key")
        except Exception as e:
            logger.error(f"Error adding management key: {e}")
            
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self._shutdown = True
        
    async def shutdown(self):
        """Shutdown the service"""
        logger.info("Shutting down SSH manager service...")
        self._shutdown = True


async def main():
    """Main entry point"""
    service = SSHManagerService()
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, service.handle_signal)
    signal.signal(signal.SIGINT, service.handle_signal)
    
    try:
        # Check if we should add a management key from environment
        mgmt_key = os.environ.get('MANAGEMENT_SSH_KEY')
        if mgmt_key:
            await service.add_management_key(mgmt_key)
            
        # Start the service
        await service.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())