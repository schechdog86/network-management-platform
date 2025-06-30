#!/usr/bin/env python3
"""
Start Ray worker with integrated management.
This replaces the shell script with a Python version that uses the Ray worker manager.
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

from ray_worker_manager import RayWorkerManager, WorkerConfig
from metrics_reporter import MetricsReporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ManagedRayWorker:
    """Managed Ray worker with monitoring and metrics"""
    
    def __init__(self):
        # Load configuration
        self.config = self._load_config()
        
        # Create worker config
        self.worker_config = WorkerConfig(
            node_id=self.config.get('NODE_ID', os.uname().nodename),
            ray_head_address=self.config.get('RAY_HEAD_ADDRESS', 'auto'),
            num_cpus=self.config.get('RAY_WORKER_CPU_CORES'),
            num_gpus=self.config.get('RAY_WORKER_GPU_NUM'),
            labels={
                'node_type': 'ai-worker',
                'snap_version': os.environ.get('SNAP_VERSION', 'unknown'),
                'managed': 'true'
            }
        )
        
        # Auto-detect GPUs if not specified
        if self.worker_config.num_gpus is None:
            self.worker_config.num_gpus = self._detect_gpus()
            
        # Create managers
        self.ray_manager = RayWorkerManager(self.worker_config)
        self.metrics_reporter = MetricsReporter(
            self.config.get('MANAGEMENT_SERVER_URL', 'http://localhost:8000'),
            self.worker_config.node_id
        )
        
        self._shutdown = False
        
    def _load_config(self) -> dict:
        """Load configuration from file and environment"""
        config = {}
        
        # Load from config file
        config_file = Path(os.environ.get('SNAP_DATA', '/var/snap/ai-worker/current')) / 'ray-worker.conf'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split('=', 1)
                            # Remove quotes
                            value = value.strip('"\'')
                            # Convert numeric values
                            if value.isdigit():
                                value = int(value)
                            config[key] = value
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                
        # Override with environment variables
        for key in ['RAY_HEAD_ADDRESS', 'RAY_WORKER_CPU_CORES', 'RAY_WORKER_GPU_NUM',
                   'MANAGEMENT_SERVER_URL', 'NODE_ID']:
            if key in os.environ:
                value = os.environ[key]
                if value.isdigit():
                    value = int(value)
                config[key] = value
                
        return config
        
    def _detect_gpus(self) -> int:
        """Auto-detect number of GPUs"""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=count', '--format=csv,noheader'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                gpu_count = int(result.stdout.strip())
                logger.info(f"Detected {gpu_count} GPU(s)")
                return gpu_count
        except Exception as e:
            logger.debug(f"GPU detection failed: {e}")
            
        return 0
        
    async def start(self):
        """Start the managed Ray worker"""
        logger.info("Starting managed Ray worker...")
        logger.info(f"Node ID: {self.worker_config.node_id}")
        logger.info(f"Ray head address: {self.worker_config.ray_head_address}")
        logger.info(f"CPUs: {self.worker_config.num_cpus}")
        logger.info(f"GPUs: {self.worker_config.num_gpus}")
        
        try:
            # Initialize Ray worker
            await self.ray_manager.initialize()
            
            # Start metrics reporter
            metrics_task = asyncio.create_task(self.metrics_reporter.start())
            
            # Register example actors if in test mode
            if self.config.get('REGISTER_TEST_ACTORS'):
                await self._register_test_actors()
                
            # Main loop - keep running until shutdown
            while not self._shutdown:
                # Report worker stats periodically
                stats = self.ray_manager.get_worker_stats()
                logger.info(f"Worker stats: Tasks={stats['tasks_completed']}, "
                          f"CPU={stats['system']['cpu_percent']}%, "
                          f"Memory={stats['system']['memory_percent']}%")
                
                await asyncio.sleep(60)  # Report every minute
                
        except Exception as e:
            logger.error(f"Error in managed worker: {e}")
            raise
        finally:
            # Cleanup
            await self.shutdown()
            
    async def _register_test_actors(self):
        """Register test actors for demonstration"""
        try:
            from ray_worker_manager import ModelServingActor
            
            # Register a test model serving actor
            await self.ray_manager.register_named_actor(
                ModelServingActor,
                f"model-server-{self.worker_config.node_id}",
                "test-model-v1"
            )
            
            logger.info("Registered test actors")
            
        except Exception as e:
            logger.error(f"Error registering test actors: {e}")
            
    async def shutdown(self):
        """Shutdown the worker gracefully"""
        logger.info("Shutting down managed Ray worker...")
        self._shutdown = True
        
        # Stop metrics reporter
        await self.metrics_reporter.stop()
        
        # Shutdown Ray
        await self.ray_manager.shutdown()
        
        logger.info("Shutdown complete")
        
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self._shutdown = True


async def main():
    """Main entry point"""
    worker = ManagedRayWorker()
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, worker.handle_signal)
    signal.signal(signal.SIGINT, worker.handle_signal)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())