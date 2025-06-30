#!/usr/bin/env python3
"""
Metrics reporting service for AI worker nodes.
Collects hardware metrics and reports them to the management server.
"""

import asyncio
import aiohttp
import json
import logging
import socket
from datetime import datetime
from typing import Dict, Any, Optional
from hardware_monitor import HardwareMonitor

logger = logging.getLogger(__name__)


class MetricsReporter:
    """Reports hardware metrics to the management server"""
    
    def __init__(self, server_url: str, node_id: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.node_id = node_id or socket.gethostname()
        self.monitor = HardwareMonitor()
        self.report_interval = 60  # seconds
        self.session: Optional[aiohttp.ClientSession] = None
        self._running = False
        
    async def start(self):
        """Start the metrics reporting service"""
        if self._running:
            logger.warning("Metrics reporter already running")
            return
            
        self._running = True
        self.session = aiohttp.ClientSession()
        
        logger.info(f"Starting metrics reporter for node {self.node_id}")
        logger.info(f"Reporting to: {self.server_url}")
        
        try:
            await self._report_loop()
        except Exception as e:
            logger.error(f"Error in metrics reporter: {e}")
        finally:
            await self.stop()
            
    async def stop(self):
        """Stop the metrics reporting service"""
        self._running = False
        if self.session:
            await self.session.close()
            self.session = None
            
    async def _report_loop(self):
        """Main reporting loop"""
        while self._running:
            try:
                # Collect metrics
                metrics = await self._collect_metrics()
                
                # Send to server
                await self._send_metrics(metrics)
                
                # Wait for next interval
                await asyncio.sleep(self.report_interval)
                
            except Exception as e:
                logger.error(f"Error in report loop: {e}")
                await asyncio.sleep(self.report_interval)
                
    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect metrics from hardware monitor"""
        try:
            # Run hardware monitoring in executor to avoid blocking
            loop = asyncio.get_event_loop()
            metrics = await loop.run_in_executor(None, self.monitor.collect_all_metrics)
            
            # Add node information
            metrics["node_id"] = self.node_id
            metrics["node_type"] = "ai-worker"
            
            # Check for high resource usage
            self._check_alerts(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
            
    def _check_alerts(self, metrics: Dict[str, Any]):
        """Check for conditions that need alerting"""
        try:
            # CPU usage alert
            cpu_usage = metrics.get("cpu", {}).get("usage_percent", 0)
            if cpu_usage > 90:
                logger.warning(f"High CPU usage: {cpu_usage}%")
                
            # Memory usage alert
            memory_percent = metrics.get("memory", {}).get("virtual", {}).get("percent", 0)
            if memory_percent > 90:
                logger.warning(f"High memory usage: {memory_percent}%")
                
            # Disk space alert
            for partition in metrics.get("disk", {}).get("partitions", []):
                if partition["usage"]["percent"] > 85:
                    logger.warning(
                        f"Low disk space on {partition['mountpoint']}: "
                        f"{partition['usage']['percent']}% used"
                    )
                    
            # GPU temperature alert
            for gpu in metrics.get("gpu", {}).get("nvidia", []):
                temp = gpu.get("temperature")
                if temp and temp > 85:
                    logger.warning(f"High GPU temperature: {temp}°C on {gpu['name']}")
                    
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            
    async def _send_metrics(self, metrics: Dict[str, Any]):
        """Send metrics to the management server"""
        if not self.session:
            return
            
        try:
            url = f"{self.server_url}/api/v1/metrics/report"
            
            async with self.session.post(
                url,
                json=metrics,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    logger.debug("Successfully reported metrics")
                else:
                    text = await response.text()
                    logger.error(f"Failed to report metrics: {response.status} - {text}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error reporting metrics: {e}")
        except Exception as e:
            logger.error(f"Error sending metrics: {e}")
            
    async def send_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Send an alert to the management server"""
        if not self.session:
            return
            
        try:
            alert_data = {
                "node_id": self.node_id,
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            url = f"{self.server_url}/api/v1/alerts/node"
            
            async with self.session.post(
                url,
                json=alert_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    logger.info(f"Alert sent: {alert_type}")
                else:
                    logger.error(f"Failed to send alert: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error sending alert: {e}")


async def main():
    """Run the metrics reporter"""
    import os
    
    # Get configuration from environment
    server_url = os.getenv("MANAGEMENT_SERVER_URL", "http://localhost:8000")
    node_id = os.getenv("NODE_ID", socket.gethostname())
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start reporter
    reporter = MetricsReporter(server_url, node_id)
    
    try:
        await reporter.start()
    except KeyboardInterrupt:
        logger.info("Shutting down metrics reporter")
        await reporter.stop()


if __name__ == "__main__":
    asyncio.run(main())