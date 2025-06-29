#!/usr/bin/env python3
"""
Hardware Monitoring Service for Ubuntu Core Network Management Client
Collects detailed hardware metrics and system information
"""

import asyncio
import logging
import os
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class HardwareMonitor:
    """Hardware monitoring service for Ubuntu Core devices"""
    
    def __init__(self):
        self.config = self._load_config()
        self.running = False
        self.metrics_cache = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load monitoring configuration"""
        return {
            'collection_interval': 60,
            'detailed_scan_interval': 300,
            'enable_smart_monitoring': True,
            'enable_temperature_monitoring': True,
            'enable_power_monitoring': True,
            'enable_network_hardware': True,
            'metrics_retention_hours': 24,
        }
    
    async def start_monitoring(self):
        """Start hardware monitoring"""
        logger.info("Starting hardware monitoring service")
        self.running = True
        
        tasks = [
            asyncio.create_task(self._basic_metrics_loop()),
            asyncio.create_task(self._detailed_scan_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Hardware monitoring stopped")
        except Exception as e:
            logger.error(f"Hardware monitoring error: {e}")
    
    async def stop_monitoring(self):
        """Stop hardware monitoring"""
        self.running = False
    
    async def _basic_metrics_loop(self):
        """Collect basic system metrics regularly"""
        while self.running:
            try:
                metrics = await self._collect_basic_metrics()
                await self._store_metrics('basic', metrics)
                await asyncio.sleep(self.config['collection_interval'])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Basic metrics collection error: {e}")
                await asyncio.sleep(30)
    
    async def _detailed_scan_loop(self):
        """Perform detailed hardware scans periodically"""
        while self.running:
            try:
                metrics = await self._collect_detailed_metrics()
                await self._store_metrics('detailed', metrics)
                await asyncio.sleep(self.config['detailed_scan_interval'])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detailed scan error: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_loop(self):
        """Cleanup old metrics files"""
        while self.running:
            try:
                await self._cleanup_old_metrics()
                await asyncio.sleep(3600)  # Cleanup every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(3600)
    
    async def _collect_basic_metrics(self) -> Dict[str, Any]:
        """Collect basic system metrics using psutil"""
        import psutil
        
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'hostname': os.uname().nodename,
            'uptime': time.time() - psutil.boot_time(),
        }
        
        # CPU metrics
        metrics['cpu'] = {
            'percent': psutil.cpu_percent(interval=1),
            'count_logical': psutil.cpu_count(logical=True),
            'count_physical': psutil.cpu_count(logical=False),
            'per_cpu': psutil.cpu_percent(interval=1, percpu=True),
            'load_avg': os.getloadavg(),
        }
        
        if hasattr(psutil, 'cpu_freq') and psutil.cpu_freq():
            metrics['cpu']['frequency'] = {
                'current': psutil.cpu_freq().current,
                'min': psutil.cpu_freq().min,
                'max': psutil.cpu_freq().max,
            }
        
        # Memory metrics
        vm = psutil.virtual_memory()
        metrics['memory'] = {
            'total': vm.total,
            'available': vm.available,
            'used': vm.used,
            'free': vm.free,
            'percent': vm.percent,
            'buffers': getattr(vm, 'buffers', 0),
            'cached': getattr(vm, 'cached', 0),
        }
        
        # Swap metrics
        swap = psutil.swap_memory()
        metrics['swap'] = {
            'total': swap.total,
            'used': swap.used,
            'free': swap.free,
            'percent': swap.percent,
        }
        
        # Disk metrics
        metrics['disk'] = {}
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                metrics['disk'][partition.device] = {
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent,
                }
            except PermissionError:
                continue
        
        # Network metrics
        net_io = psutil.net_io_counters()
        metrics['network'] = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout,
            'dropin': net_io.dropin,
            'dropout': net_io.dropout,
        }
        
        # Network interfaces
        metrics['network_interfaces'] = {}
        for interface, addrs in psutil.net_if_addrs().items():
            stats = psutil.net_if_stats().get(interface)
            metrics['network_interfaces'][interface] = {
                'addresses': [
                    {
                        'family': addr.family.name,
                        'address': addr.address,
                        'netmask': addr.netmask,
                        'broadcast': addr.broadcast,
                    }
                    for addr in addrs
                ],
                'is_up': stats.isup if stats else False,
                'duplex': stats.duplex.name if stats and hasattr(stats.duplex, 'name') else 'unknown',
                'speed': stats.speed if stats else 0,
                'mtu': stats.mtu if stats else 0,
            }
        
        return metrics
    
    async def _collect_detailed_metrics(self) -> Dict[str, Any]:
        """Collect detailed hardware information"""
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'hardware_info': await self._get_hardware_info(),
            'pci_devices': await self._get_pci_devices(),
            'usb_devices': await self._get_usb_devices(),
            'block_devices': await self._get_block_devices(),
        }
        
        if self.config['enable_smart_monitoring']:
            metrics['smart_data'] = await self._get_smart_data()
        
        if self.config['enable_temperature_monitoring']:
            metrics['temperatures'] = await self._get_temperatures()
        
        if self.config['enable_power_monitoring']:
            metrics['power'] = await self._get_power_info()
        
        return metrics
    
    async def _get_hardware_info(self) -> Dict[str, Any]:
        """Get general hardware information"""
        hardware = {}
        
        # CPU information
        try:
            result = await self._run_command(['lscpu'])
            if result['success']:
                hardware['cpu_info'] = result['output']
        except Exception as e:
            logger.warning(f"Failed to get CPU info: {e}")
        
        # Memory information
        try:
            with open('/proc/meminfo', 'r') as f:
                hardware['meminfo'] = f.read()
        except Exception as e:
            logger.warning(f"Failed to read meminfo: {e}")
        
        # DMI information
        try:
            result = await self._run_command(['dmidecode', '-t', 'system'])
            if result['success']:
                hardware['system_info'] = result['output']
        except Exception as e:
            logger.warning(f"Failed to get DMI info: {e}")
        
        # Hardware overview
        try:
            result = await self._run_command(['lshw', '-short'])
            if result['success']:
                hardware['hardware_overview'] = result['output']
        except Exception as e:
            logger.warning(f"Failed to get hardware overview: {e}")
        
        return hardware
    
    async def _get_pci_devices(self) -> List[Dict[str, Any]]:
        """Get PCI device information"""
        devices = []
        
        try:
            result = await self._run_command(['lspci', '-v'])
            if result['success']:
                current_device = {}
                for line in result['output'].split('\n'):
                    if line and not line.startswith('\t'):
                        if current_device:
                            devices.append(current_device)
                        current_device = {'description': line.strip()}
                    elif line.startswith('\t'):
                        if ':' in line:
                            key, value = line.strip().split(':', 1)
                            current_device[key.strip()] = value.strip()
                
                if current_device:
                    devices.append(current_device)
        except Exception as e:
            logger.warning(f"Failed to get PCI devices: {e}")
        
        return devices
    
    async def _get_usb_devices(self) -> List[Dict[str, Any]]:
        """Get USB device information"""
        devices = []
        
        try:
            result = await self._run_command(['lsusb', '-v'])
            if result['success']:
                # Parse USB device information
                # This is a simplified parser
                for line in result['output'].split('\n'):
                    if line.startswith('Bus'):
                        devices.append({'description': line.strip()})
        except Exception as e:
            logger.warning(f"Failed to get USB devices: {e}")
        
        return devices
    
    async def _get_block_devices(self) -> List[Dict[str, Any]]:
        """Get block device information"""
        devices = []
        
        try:
            result = await self._run_command(['lsblk', '-J'])
            if result['success']:
                import json
                block_data = json.loads(result['output'])
                devices = block_data.get('blockdevices', [])
        except Exception as e:
            logger.warning(f"Failed to get block devices: {e}")
        
        return devices
    
    async def _get_smart_data(self) -> Dict[str, Any]:
        """Get SMART data for storage devices"""
        smart_data = {}
        
        # Get list of storage devices
        try:
            result = await self._run_command(['lsblk', '-d', '-o', 'NAME,TYPE'])
            if result['success']:
                for line in result['output'].split('\n')[1:]:  # Skip header
                    if 'disk' in line:
                        device_name = line.split()[0]
                        device_path = f'/dev/{device_name}'
                        
                        # Get SMART data for this device
                        smart_result = await self._run_command(['smartctl', '-a', device_path])
                        if smart_result['success']:
                            smart_data[device_name] = smart_result['output']
        except Exception as e:
            logger.warning(f"Failed to get SMART data: {e}")
        
        return smart_data
    
    async def _get_temperatures(self) -> Dict[str, Any]:
        """Get temperature sensor data"""
        temperatures = {}
        
        try:
            # Using psutil for temperature data
            import psutil
            if hasattr(psutil, 'sensors_temperatures'):
                temp_data = psutil.sensors_temperatures()
                for sensor_name, sensor_list in temp_data.items():
                    temperatures[sensor_name] = [
                        {
                            'label': temp.label or 'unlabeled',
                            'current': temp.current,
                            'high': temp.high,
                            'critical': temp.critical,
                        }
                        for temp in sensor_list
                    ]
        except Exception as e:
            logger.warning(f"Failed to get temperature data: {e}")
        
        return temperatures
    
    async def _get_power_info(self) -> Dict[str, Any]:
        """Get power and battery information"""
        power_info = {}
        
        try:
            import psutil
            if hasattr(psutil, 'sensors_battery'):
                battery = psutil.sensors_battery()
                if battery:
                    power_info['battery'] = {
                        'percent': battery.percent,
                        'plugged_in': battery.power_plugged,
                        'time_left': battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                    }
        except Exception as e:
            logger.warning(f"Failed to get power info: {e}")
        
        return power_info
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run system command asynchronously"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                'success': process.returncode == 0,
                'output': stdout.decode('utf-8', errors='ignore'),
                'error': stderr.decode('utf-8', errors='ignore'),
                'return_code': process.returncode,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'return_code': -1,
            }
    
    async def _store_metrics(self, metric_type: str, data: Dict[str, Any]):
        """Store metrics to local storage"""
        try:
            metrics_dir = Path(os.environ.get('SNAP_DATA', '/var/snap/network-mgmt-client/current')) / 'metrics' / 'hardware'
            metrics_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H')
            metrics_file = metrics_dir / f"{metric_type}_{timestamp}.json"
            
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
                
        except Exception as e:
            logger.warning(f"Failed to store hardware metrics: {e}")
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics files"""
        try:
            metrics_dir = Path(os.environ.get('SNAP_DATA', '/var/snap/network-mgmt-client/current')) / 'metrics'
            if not metrics_dir.exists():
                return
            
            cutoff_time = time.time() - (self.config['metrics_retention_hours'] * 3600)
            
            for metrics_file in metrics_dir.rglob('*.json'):
                if metrics_file.stat().st_mtime < cutoff_time:
                    metrics_file.unlink()
                    logger.debug(f"Removed old metrics file: {metrics_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old metrics: {e}")

async def main():
    """Main entry point for hardware monitor"""
    logging.basicConfig(level=logging.INFO)
    
    monitor = HardwareMonitor()
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await monitor.stop_monitoring()

if __name__ == '__main__':
    asyncio.run(main())