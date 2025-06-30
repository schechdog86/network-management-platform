#!/usr/bin/env python3
"""
GPU monitoring daemon for AI worker nodes.
Monitors GPU health and performance, triggers alerts on issues.
"""

import os
import sys
import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.environ.get('SNAP', ''), 'lib/ai-worker'))

from hardware_monitor import HardwareMonitor
from metrics_reporter import MetricsReporter

logger = logging.getLogger(__name__)


class GPUMonitor:
    """GPU monitoring and alerting service"""
    
    def __init__(self, server_url: str, node_id: str):
        self.hardware_monitor = HardwareMonitor()
        self.metrics_reporter = MetricsReporter(server_url, node_id)
        self.check_interval = 30  # seconds
        self.alert_thresholds = {
            "temperature": 85,  # Celsius
            "memory_usage": 90,  # Percentage
            "power_ratio": 0.95,  # Power draw / limit ratio
        }
        self._running = False
        
    async def start(self):
        """Start GPU monitoring"""
        if self._running:
            logger.warning("GPU monitor already running")
            return
            
        self._running = True
        logger.info("Starting GPU monitoring service")
        
        # Start metrics reporter session
        self.metrics_reporter.session = aiohttp.ClientSession()
        
        try:
            await self._monitor_loop()
        except Exception as e:
            logger.error(f"Error in GPU monitor: {e}")
        finally:
            await self.stop()
            
    async def stop(self):
        """Stop GPU monitoring"""
        self._running = False
        if self.metrics_reporter.session:
            await self.metrics_reporter.session.close()
            
    async def _monitor_loop(self):
        """Main monitoring loop"""
        consecutive_failures = 0
        
        while self._running:
            try:
                # Get GPU info
                loop = asyncio.get_event_loop()
                gpu_info = await loop.run_in_executor(
                    None, self.hardware_monitor.get_gpu_info
                )
                
                if gpu_info and "nvidia" in gpu_info:
                    consecutive_failures = 0
                    await self._check_gpu_health(gpu_info["nvidia"])
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        await self.metrics_reporter.send_alert(
                            "gpu_unavailable",
                            "No GPU detected or nvidia-smi not responding",
                            "warning"
                        )
                        consecutive_failures = 0  # Reset to avoid spam
                        
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _check_gpu_health(self, gpus: List[Dict[str, Any]]):
        """Check GPU health and trigger alerts"""
        for i, gpu in enumerate(gpus):
            gpu_name = gpu.get("name", f"GPU {i}")
            
            # Temperature check
            temp = gpu.get("temperature")
            if temp and temp > self.alert_thresholds["temperature"]:
                await self.metrics_reporter.send_alert(
                    "gpu_temperature",
                    f"{gpu_name} temperature is {temp}°C (threshold: {self.alert_thresholds['temperature']}°C)",
                    "critical" if temp > 90 else "warning"
                )
                
            # Memory usage check
            if gpu.get("memory_total") and gpu.get("memory_used"):
                memory_percent = (gpu["memory_used"] / gpu["memory_total"]) * 100
                if memory_percent > self.alert_thresholds["memory_usage"]:
                    await self.metrics_reporter.send_alert(
                        "gpu_memory",
                        f"{gpu_name} memory usage is {memory_percent:.1f}% ({gpu['memory_used']:.0f}/{gpu['memory_total']:.0f} MB)",
                        "warning"
                    )
                    
            # Power usage check
            if gpu.get("power_draw") and gpu.get("power_limit"):
                power_ratio = gpu["power_draw"] / gpu["power_limit"]
                if power_ratio > self.alert_thresholds["power_ratio"]:
                    await self.metrics_reporter.send_alert(
                        "gpu_power",
                        f"{gpu_name} power draw is {gpu['power_draw']:.1f}W of {gpu['power_limit']:.1f}W limit ({power_ratio*100:.1f}%)",
                        "warning"
                    )
                    
            # Log current status
            logger.info(
                f"{gpu_name}: Temp={temp}°C, "
                f"GPU={gpu.get('utilization_gpu', 0)}%, "
                f"Mem={gpu.get('memory_used', 0):.0f}/{gpu.get('memory_total', 0):.0f}MB, "
                f"Power={gpu.get('power_draw', 0):.1f}W"
            )


async def main():
    """Run the GPU monitor"""
    import aiohttp
    
    # Get configuration from environment
    server_url = os.getenv("MANAGEMENT_SERVER_URL", "http://localhost:8000")
    node_id = os.getenv("NODE_ID", socket.gethostname())
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check for GPU
    monitor = HardwareMonitor()
    if not monitor.has_nvidia_gpu:
        logger.warning("No NVIDIA GPU detected, exiting GPU monitor")
        return
        
    # Create and start monitor
    gpu_monitor = GPUMonitor(server_url, node_id)
    
    try:
        await gpu_monitor.start()
    except KeyboardInterrupt:
        logger.info("Shutting down GPU monitor")
        await gpu_monitor.stop()


if __name__ == "__main__":
    import socket
    import aiohttp
    asyncio.run(main())