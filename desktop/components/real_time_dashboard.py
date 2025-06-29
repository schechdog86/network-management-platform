"""
Enhanced Real-time Monitoring Dashboard with Live Metrics
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QGroupBox, QComboBox, QPushButton,
                               QSplitter, QTabWidget)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QDateTime
from PySide6.QtGui import QFont, QPalette
import pyqtgraph as pg
from collections import deque
from desktop.utils.api_client import get_api_client
import numpy as np

# Configure pyqtgraph for better performance
pg.setConfigOptions(antialias=True, useOpenGL=True)

class RealTimeDashboard(QWidget):
    """Enhanced real-time monitoring dashboard"""
    
    metrics_updated = Signal(dict)
    alert_triggered = Signal(str, str)  # message, severity
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.api_client = get_api_client(config.get("api.base_url"))
        self.update_interval = 1000  # 1 second default
        self.data_retention = 300  # Keep 5 minutes of data
        self.devices = {}
        self.setup_ui()
        self.setup_timers()
        self.initialize_data_structures()
        
    def setup_ui(self):
        """Setup the dashboard UI"""
        layout = QVBoxLayout(self)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        title = QLabel("Real-time System Monitoring")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Update interval control
        header_layout.addWidget(QLabel("Update:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["0.5s", "1s", "2s", "5s", "10s"])
        self.interval_combo.setCurrentText("1s")
        self.interval_combo.currentTextChanged.connect(self.change_update_interval)
        header_layout.addWidget(self.interval_combo)
        
        # Device selector
        header_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItem("All Devices")
        self.device_combo.currentTextChanged.connect(self.change_device_filter)
        header_layout.addWidget(self.device_combo)
        
        # Pause/Resume button
        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self.toggle_updates)
        header_layout.addWidget(self.pause_button)
        
        layout.addLayout(header_layout)
        
        # Main content area with splitter
        splitter = QSplitter(Qt.Vertical)
        
        # System overview section
        overview_widget = self.create_overview_section()
        splitter.addWidget(overview_widget)
        
        # Detailed metrics section
        metrics_widget = self.create_metrics_section()
        splitter.addWidget(metrics_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
    def create_overview_section(self):
        """Create system overview section"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # CPU gauge
        self.cpu_gauge = CircularGauge("CPU Usage", "%")
        layout.addWidget(self.cpu_gauge, 0, 0)
        
        # Memory gauge
        self.memory_gauge = CircularGauge("Memory", "%")
        layout.addWidget(self.memory_gauge, 0, 1)
        
        # Disk gauge
        self.disk_gauge = CircularGauge("Disk", "%")
        layout.addWidget(self.disk_gauge, 0, 2)
        
        # Network status
        self.network_status = NetworkStatusWidget()
        layout.addWidget(self.network_status, 0, 3)
        
        # System health indicator
        self.health_indicator = SystemHealthIndicator()
        layout.addWidget(self.health_indicator, 1, 0, 1, 4)
        
        return widget
        
    def create_metrics_section(self):
        """Create detailed metrics section"""
        tabs = QTabWidget()
        
        # CPU/Memory tab
        self.resource_plot = ResourcePlotWidget()
        tabs.addTab(self.resource_plot, "CPU & Memory")
        
        # Network tab
        self.network_plot = NetworkPlotWidget()
        tabs.addTab(self.network_plot, "Network")
        
        # Disk I/O tab
        self.disk_plot = DiskIOPlotWidget()
        tabs.addTab(self.disk_plot, "Disk I/O")
        
        # Process monitor tab
        self.process_monitor = ProcessMonitorWidget()
        tabs.addTab(self.process_monitor, "Processes")
        
        return tabs
        
    def setup_timers(self):
        """Setup update timers"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_metrics)
        self.update_timer.start(self.update_interval)
        
    def initialize_data_structures(self):
        """Initialize data storage"""
        self.metrics_history = {
            'timestamps': deque(maxlen=self.data_retention),
            'cpu': deque(maxlen=self.data_retention),
            'memory': deque(maxlen=self.data_retention),
            'disk': deque(maxlen=self.data_retention),
            'network_in': deque(maxlen=self.data_retention),
            'network_out': deque(maxlen=self.data_retention),
        }
        
    @Slot()
    def update_metrics(self):
        """Fetch and update metrics"""
        if self.pause_button.isChecked():
            return
            
        # Get current device filter
        device_filter = self.device_combo.currentText()
        device_id = None if device_filter == "All Devices" else device_filter
        
        # Fetch metrics from API
        result = self.api_client.get_metrics(device_id)
        
        if result.get("success"):
            self.process_metrics(result.get("data", {}))
        else:
            # Use simulated data as fallback
            self.process_simulated_metrics()
            
    def process_metrics(self, metrics_data):
        """Process and display metrics"""
        timestamp = QDateTime.currentDateTime().toMSecsSinceEpoch() / 1000
        
        if isinstance(metrics_data, dict):
            # Single device metrics
            cpu_percent = metrics_data.get("cpu_percent", 0)
            memory_percent = metrics_data.get("memory_percent", 0)
            disk_percent = metrics_data.get("disk_percent", 0)
            network_bytes_recv = metrics_data.get("network", {}).get("bytes_recv", 0)
            network_bytes_sent = metrics_data.get("network", {}).get("bytes_sent", 0)
            
            # Update gauges
            self.cpu_gauge.set_value(cpu_percent)
            self.memory_gauge.set_value(memory_percent)
            self.disk_gauge.set_value(disk_percent)
            
            # Update network status
            self.network_status.update_stats(network_bytes_recv, network_bytes_sent)
            
            # Add to history
            self.metrics_history['timestamps'].append(timestamp)
            self.metrics_history['cpu'].append(cpu_percent)
            self.metrics_history['memory'].append(memory_percent)
            self.metrics_history['disk'].append(disk_percent)
            self.metrics_history['network_in'].append(network_bytes_recv / 1024 / 1024)  # MB
            self.metrics_history['network_out'].append(network_bytes_sent / 1024 / 1024)
            
            # Update plots
            self.update_plots()
            
            # Check for alerts
            self.check_alerts(metrics_data)
            
            # Update device list if needed
            self.update_device_list(metrics_data)
            
        elif isinstance(metrics_data, list):
            # Multiple device metrics - aggregate or show selected
            self.process_multi_device_metrics(metrics_data)
            
    def process_simulated_metrics(self):
        """Generate simulated metrics for testing"""
        import random
        timestamp = QDateTime.currentDateTime().toMSecsSinceEpoch() / 1000
        
        # Generate simulated values
        cpu = random.uniform(20, 80)
        memory = random.uniform(40, 90)
        disk = random.uniform(30, 70)
        net_in = random.uniform(10, 100)
        net_out = random.uniform(5, 50)
        
        # Update gauges
        self.cpu_gauge.set_value(cpu)
        self.memory_gauge.set_value(memory)
        self.disk_gauge.set_value(disk)
        
        # Update network
        self.network_status.update_stats(net_in * 1024 * 1024, net_out * 1024 * 1024)
        
        # Add to history
        self.metrics_history['timestamps'].append(timestamp)
        self.metrics_history['cpu'].append(cpu)
        self.metrics_history['memory'].append(memory)
        self.metrics_history['disk'].append(disk)
        self.metrics_history['network_in'].append(net_in)
        self.metrics_history['network_out'].append(net_out)
        
        # Update plots
        self.update_plots()
        
    def update_plots(self):
        """Update all plot widgets"""
        if len(self.metrics_history['timestamps']) > 1:
            # Convert timestamps to relative seconds
            timestamps = list(self.metrics_history['timestamps'])
            current_time = timestamps[-1]
            time_axis = [t - current_time for t in timestamps]
            
            # Update resource plot
            self.resource_plot.update_data(
                time_axis,
                list(self.metrics_history['cpu']),
                list(self.metrics_history['memory'])
            )
            
            # Update network plot
            self.network_plot.update_data(
                time_axis,
                list(self.metrics_history['network_in']),
                list(self.metrics_history['network_out'])
            )
            
    def check_alerts(self, metrics):
        """Check for alert conditions"""
        # CPU alert
        cpu_percent = metrics.get("cpu_percent", 0)
        if cpu_percent > 90:
            self.alert_triggered.emit(f"High CPU usage: {cpu_percent:.1f}%", "critical")
        elif cpu_percent > 80:
            self.alert_triggered.emit(f"Elevated CPU usage: {cpu_percent:.1f}%", "warning")
            
        # Memory alert
        memory_percent = metrics.get("memory_percent", 0)
        if memory_percent > 90:
            self.alert_triggered.emit(f"High memory usage: {memory_percent:.1f}%", "critical")
        elif memory_percent > 80:
            self.alert_triggered.emit(f"Elevated memory usage: {memory_percent:.1f}%", "warning")
            
        # Disk alert
        disk_percent = metrics.get("disk_percent", 0)
        if disk_percent > 95:
            self.alert_triggered.emit(f"Critical disk space: {disk_percent:.1f}% used", "critical")
        elif disk_percent > 85:
            self.alert_triggered.emit(f"Low disk space: {disk_percent:.1f}% used", "warning")
            
        # Update health indicator
        self.health_indicator.update_health(cpu_percent, memory_percent, disk_percent)
        
    def update_device_list(self, metrics):
        """Update device combo box"""
        device_name = metrics.get("hostname", metrics.get("device_id", "Unknown"))
        if device_name not in self.devices:
            self.devices[device_name] = True
            self.device_combo.addItem(device_name)
            
    def process_multi_device_metrics(self, metrics_list):
        """Process metrics for multiple devices"""
        # Aggregate or filter based on selection
        selected_device = self.device_combo.currentText()
        
        if selected_device == "All Devices":
            # Calculate averages
            cpu_avg = np.mean([m.get("cpu_percent", 0) for m in metrics_list])
            memory_avg = np.mean([m.get("memory_percent", 0) for m in metrics_list])
            disk_avg = np.mean([m.get("disk_percent", 0) for m in metrics_list])
            
            self.cpu_gauge.set_value(cpu_avg)
            self.memory_gauge.set_value(memory_avg)
            self.disk_gauge.set_value(disk_avg)
        else:
            # Find specific device
            for metrics in metrics_list:
                if metrics.get("hostname") == selected_device:
                    self.process_metrics(metrics)
                    break
                    
    @Slot(str)
    def change_update_interval(self, interval_text):
        """Change update interval"""
        if interval_text.endswith('s'):
            interval = float(interval_text[:-1]) * 1000
            self.update_interval = int(interval)
            self.update_timer.setInterval(self.update_interval)
            
    @Slot(str)
    def change_device_filter(self, device):
        """Change device filter"""
        # Clear history when changing device
        self.initialize_data_structures()
        
    @Slot(bool)
    def toggle_updates(self, paused):
        """Toggle metric updates"""
        if paused:
            self.pause_button.setText("Resume")
        else:
            self.pause_button.setText("Pause")
            
    def update_from_websocket(self, data):
        """Update from WebSocket data"""
        if isinstance(data, dict) and not self.pause_button.isChecked():
            self.process_metrics(data)


class CircularGauge(QWidget):
    """Circular gauge widget for metrics"""
    
    def __init__(self, title, unit):
        super().__init__()
        self.title = title
        self.unit = unit
        self.value = 0
        self.setMinimumSize(150, 150)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Gauge plot
        self.plot = pg.PlotWidget()
        self.plot.setAspectLocked(True)
        self.plot.hideAxis('left')
        self.plot.hideAxis('bottom')
        self.plot.setBackground(None)
        
        # Draw gauge background
        self.draw_gauge()
        
        layout.addWidget(self.plot)
        
        # Value label
        self.value_label = QLabel("0%")
        self.value_label.setAlignment(Qt.AlignCenter)
        value_font = QFont()
        value_font.setPointSize(16)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        layout.addWidget(self.value_label)
        
        # Title label
        title_label = QLabel(self.title)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
    def draw_gauge(self):
        """Draw gauge background and needle"""
        # Clear plot
        self.plot.clear()
        
        # Draw arc background
        theta = np.linspace(-np.pi * 0.75, np.pi * 0.75, 100)
        radius = 1
        x = radius * np.cos(theta)
        y = radius * np.sin(theta)
        
        # Background arc
        self.plot.plot(x, y, pen=pg.mkPen(color=(100, 100, 100), width=10))
        
        # Value arc
        value_theta = -np.pi * 0.75 + (self.value / 100) * (np.pi * 1.5)
        value_theta_range = np.linspace(-np.pi * 0.75, value_theta, 50)
        value_x = radius * np.cos(value_theta_range)
        value_y = radius * np.sin(value_theta_range)
        
        # Color based on value
        if self.value < 60:
            color = (0, 255, 0)  # Green
        elif self.value < 80:
            color = (255, 255, 0)  # Yellow
        else:
            color = (255, 0, 0)  # Red
            
        self.plot.plot(value_x, value_y, pen=pg.mkPen(color=color, width=10))
        
        # Center dot
        self.plot.plot([0], [0], pen=None, symbol='o', symbolSize=20, symbolBrush=(50, 50, 50))
        
    def set_value(self, value):
        """Set gauge value"""
        self.value = max(0, min(100, value))
        self.value_label.setText(f"{self.value:.1f}{self.unit}")
        self.draw_gauge()


class NetworkStatusWidget(QGroupBox):
    """Network status display widget"""
    
    def __init__(self):
        super().__init__("Network")
        self.last_recv = 0
        self.last_sent = 0
        self.last_time = QDateTime.currentDateTime()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Download speed
        self.download_label = QLabel("↓ 0.0 MB/s")
        self.download_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.download_label)
        
        # Upload speed
        self.upload_label = QLabel("↑ 0.0 MB/s")
        self.upload_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.upload_label)
        
    def update_stats(self, bytes_recv, bytes_sent):
        """Update network statistics"""
        current_time = QDateTime.currentDateTime()
        time_diff = self.last_time.msecsTo(current_time) / 1000.0
        
        if time_diff > 0 and self.last_recv > 0:
            # Calculate speeds
            download_speed = (bytes_recv - self.last_recv) / time_diff / 1024 / 1024
            upload_speed = (bytes_sent - self.last_sent) / time_diff / 1024 / 1024
            
            self.download_label.setText(f"↓ {download_speed:.1f} MB/s")
            self.upload_label.setText(f"↑ {upload_speed:.1f} MB/s")
            
        self.last_recv = bytes_recv
        self.last_sent = bytes_sent
        self.last_time = current_time


class SystemHealthIndicator(QWidget):
    """System health indicator widget"""
    
    def __init__(self):
        super().__init__()
        self.health_score = 100
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Health label
        self.health_label = QLabel("System Health: ")
        layout.addWidget(self.health_label)
        
        # Health bar
        self.health_bar = pg.ProgressWidget()
        self.health_bar.setMinimumHeight(20)
        layout.addWidget(self.health_bar)
        
        # Status label
        self.status_label = QLabel("Excellent")
        self.status_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.status_label)
        
    def update_health(self, cpu, memory, disk):
        """Update health score based on metrics"""
        # Simple health calculation
        cpu_score = max(0, 100 - cpu)
        memory_score = max(0, 100 - memory)
        disk_score = max(0, 100 - disk)
        
        self.health_score = (cpu_score + memory_score + disk_score) / 3
        
        # Update display
        self.health_bar.setValue(int(self.health_score))
        
        if self.health_score >= 80:
            status = "Excellent"
            color = "green"
        elif self.health_score >= 60:
            status = "Good"
            color = "yellow"
        elif self.health_score >= 40:
            status = "Fair"
            color = "orange"
        else:
            status = "Poor"
            color = "red"
            
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")


class ResourcePlotWidget(QWidget):
    """CPU and Memory plot widget"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create plot
        self.plot = pg.PlotWidget()
        self.plot.setLabel('left', 'Usage', units='%')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(True, True, alpha=0.3)
        self.plot.setYRange(0, 100)
        self.plot.addLegend()
        
        # Create plot lines
        self.cpu_line = self.plot.plot(pen=pg.mkPen(color=(255, 100, 100), width=2), name='CPU')
        self.memory_line = self.plot.plot(pen=pg.mkPen(color=(100, 100, 255), width=2), name='Memory')
        
        layout.addWidget(self.plot)
        
    def update_data(self, time_axis, cpu_data, memory_data):
        """Update plot data"""
        if len(time_axis) > 0:
            self.cpu_line.setData(time_axis, cpu_data)
            self.memory_line.setData(time_axis, memory_data)


class NetworkPlotWidget(QWidget):
    """Network traffic plot widget"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create plot
        self.plot = pg.PlotWidget()
        self.plot.setLabel('left', 'Speed', units='MB/s')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(True, True, alpha=0.3)
        self.plot.addLegend()
        
        # Create plot lines
        self.download_line = self.plot.plot(pen=pg.mkPen(color=(100, 255, 100), width=2), name='Download')
        self.upload_line = self.plot.plot(pen=pg.mkPen(color=(255, 255, 100), width=2), name='Upload')
        
        layout.addWidget(self.plot)
        
    def update_data(self, time_axis, download_data, upload_data):
        """Update plot data"""
        if len(time_axis) > 0:
            self.download_line.setData(time_axis, download_data)
            self.upload_line.setData(time_axis, upload_data)


class DiskIOPlotWidget(QWidget):
    """Disk I/O plot widget"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create plot
        self.plot = pg.PlotWidget()
        self.plot.setLabel('left', 'I/O Rate', units='MB/s')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(True, True, alpha=0.3)
        self.plot.addLegend()
        
        # Create plot lines
        self.read_line = self.plot.plot(pen=pg.mkPen(color=(100, 200, 255), width=2), name='Read')
        self.write_line = self.plot.plot(pen=pg.mkPen(color=(255, 150, 100), width=2), name='Write')
        
        layout.addWidget(self.plot)


class ProcessMonitorWidget(QWidget):
    """Process monitoring widget"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Process table would go here
        info_label = QLabel("Process monitoring coming soon...")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)