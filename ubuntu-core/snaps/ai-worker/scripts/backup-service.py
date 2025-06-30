#!/usr/bin/env python3
"""
Backup service for AI worker nodes.
Performs scheduled backups and manages retention.
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.environ.get('SNAP', ''), 'lib/ai-worker'))

from backup_manager import BackupManager

logger = logging.getLogger(__name__)


class BackupService:
    """Scheduled backup service"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.backup_manager = BackupManager()
        self.config = self._load_config(config_path)
        self._running = False
        
        # Default schedule (daily at 2 AM)
        self.schedule = self.config.get('schedule', {
            'daily': {'hour': 2, 'minute': 0},
            'weekly': {'day': 0, 'hour': 3, 'minute': 0},  # Sunday
            'monthly': {'day': 1, 'hour': 4, 'minute': 0}  # 1st of month
        })
        
        # Remote backup configuration
        self.remote_config = self.config.get('remote', {})
        
    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from file"""
        if not config_path:
            config_path = os.path.join(
                os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current'),
                'config',
                'backup.json'
            )
            
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                
        return {}
        
    async def start(self):
        """Start the backup service"""
        if self._running:
            logger.warning("Backup service already running")
            return
            
        self._running = True
        logger.info("Starting backup service")
        
        # Perform initial backup if configured
        if self.config.get('initial_backup', True):
            await self._perform_backup('initial')
            
        # Start scheduled backup loop
        await self._schedule_loop()
        
    async def stop(self):
        """Stop the backup service"""
        self._running = False
        logger.info("Stopping backup service")
        
    async def _schedule_loop(self):
        """Main scheduling loop"""
        last_daily = None
        last_weekly = None
        last_monthly = None
        
        while self._running:
            now = datetime.now()
            
            # Check daily backup
            if self._should_run_backup('daily', now, last_daily):
                await self._perform_backup('daily')
                last_daily = now
                
            # Check weekly backup
            if self._should_run_backup('weekly', now, last_weekly):
                await self._perform_backup('weekly')
                last_weekly = now
                
            # Check monthly backup
            if self._should_run_backup('monthly', now, last_monthly):
                await self._perform_backup('monthly')
                last_monthly = now
                
            # Sleep for a minute before checking again
            await asyncio.sleep(60)
            
    def _should_run_backup(self, backup_type: str, now: datetime, 
                          last_run: Optional[datetime]) -> bool:
        """Check if backup should run"""
        if backup_type not in self.schedule:
            return False
            
        schedule = self.schedule[backup_type]
        
        # Check if we've already run today
        if last_run and last_run.date() == now.date():
            return False
            
        # Check schedule
        if backup_type == 'daily':
            return (now.hour == schedule['hour'] and 
                   now.minute == schedule['minute'])
                   
        elif backup_type == 'weekly':
            return (now.weekday() == schedule['day'] and
                   now.hour == schedule['hour'] and
                   now.minute == schedule['minute'])
                   
        elif backup_type == 'monthly':
            return (now.day == schedule['day'] and
                   now.hour == schedule['hour'] and
                   now.minute == schedule['minute'])
                   
        return False
        
    async def _perform_backup(self, backup_type: str):
        """Perform a backup"""
        logger.info(f"Starting {backup_type} backup")
        
        try:
            # Determine what to backup based on type
            items = None
            if backup_type == 'daily':
                # Daily backups exclude large model files
                items = ['configs', 'logs', 'ray_data']
            elif backup_type in ['weekly', 'monthly', 'initial']:
                # Full backups include everything
                items = None  # Backup all items
                
            # Create local backup
            result = await self.backup_manager.create_backup(
                items=items,
                backup_type=backup_type
            )
            
            if result.get('errors'):
                logger.error(f"Backup completed with errors: {result['errors']}")
            else:
                logger.info(f"Backup completed successfully: {result['backup_name']}")
                
            # Upload to remote if configured
            if self.remote_config.get('enabled') and backup_type != 'daily':
                await self._upload_to_remote(result['backup_name'])
                
        except Exception as e:
            logger.error(f"Error performing {backup_type} backup: {e}")
            
    async def _upload_to_remote(self, backup_name: str):
        """Upload backup to remote storage"""
        try:
            remote_url = self.remote_config.get('url')
            method = self.remote_config.get('method', 'rsync')
            
            if not remote_url:
                logger.warning("Remote backup enabled but no URL configured")
                return
                
            logger.info(f"Uploading {backup_name} to {remote_url}")
            
            result = await self.backup_manager.backup_to_remote(
                backup_name,
                remote_url,
                method
            )
            
            if result['status'] == 'completed':
                logger.info(f"Successfully uploaded backup to {remote_url}")
            else:
                logger.error(f"Failed to upload backup: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error uploading backup: {e}")


async def main():
    """Run the backup service"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get config path from environment
    config_path = os.environ.get('BACKUP_CONFIG_PATH')
    
    # Create and start service
    service = BackupService(config_path)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Shutting down backup service")
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())