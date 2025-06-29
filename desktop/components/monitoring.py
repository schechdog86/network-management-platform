"""
Monitoring Widget - Real-time network monitoring
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QTabWidget, QLabel, QComboBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
import pyqtgraph as pg
from desktop.utils.api_client import get_api_client
import time

class MonitoringWidget(QWidget):
    metric_updated = Signal(str, float)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
        self.setup_timers()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Control bar
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("Update Interval:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1s", "5s", "10s", "30s", "1m"])
        self.interval_combo.setCurrentText("5s")
        self.interval_combo.currentTextChanged.connect(self.update_interval)
        control_layout.addWidget(self.interval_combo)
        
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # Tabs for different metrics
        self.tabs = QTabWidget()
        
        # Network traffic tab
        self.traffic_widget = NetworkTrafficWidget()
        self.tabs.addTab(self.traffic_widget, "Network Traffic")
        
        # CPU/Memory tab
        self.resources_widget = ResourceMonitorWidget()
        self.tabs.addTab(self.resources_widget, "Resources")
        
        # Alerts tab
        self.alerts_widget = AlertsWidget()
        self.tabs.addTab(self.alerts_widget, "Alerts")
        
        layout.addWidget(self.tabs)
        
    def setup_timers(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_metrics)
        self.update_timer.start(5000)  # Default 5 seconds
        
    @Slot(str)
    def update_interval(self, interval_text):
        # Parse interval
        if interval_text.endswith('s'):
            interval = int(interval_text[:-1]) * 1000
        elif interval_text.endswith('m'):
            interval = int(interval_text[:-1]) * 60 * 1000
        else:
            interval = 5000
            
        self.update_timer.setInterval(interval)
        
    @Slot()
    def update_metrics(self):
        # Update all monitoring widgets
        self.traffic_widget.update_data()
        self.resources_widget.update_data()
        self.alerts_widget.check_alerts()
        
    def update_with_data(self, data):
        """Update widgets with real-time data from WebSocket"""
        if isinstance(data, dict):
            if "network" in data:
                self.traffic_widget.update_with_network_data(data["network"])
            if "resources" in data:
                self.resources_widget.update_with_resource_data(data["resources"])
            if "alerts" in data:
                self.alerts_widget.update_with_alerts(data["alerts"])
        
    def refresh(self):
        self.update_metrics()


class NetworkTrafficWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.init_data()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Bandwidth', units='Mbps')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.showGrid(True, True)
        self.plot_widget.setBackground('w')
        
        # Add legend
        self.plot_widget.addLegend()
        
        # Create plot lines
        self.incoming_plot = self.plot_widget.plot(pen='b', name='Incoming')
        self.outgoing_plot = self.plot_widget.plot(pen='r', name='Outgoing')
        
        layout.addWidget(self.plot_widget)
        
    def init_data(self):
        self.time_data = list(range(60))
        self.incoming_data = [0] * 60
        self.outgoing_data = [0] * 60
        
    def update_data(self):
        # Try to get real data from API
        api_client = get_api_client()
        result = api_client.get_metrics()
        
        if result.get("success") and result.get("data"):
            metrics = result.get("data", {})
            # Extract network metrics
            if "network" in metrics:
                network_data = metrics["network"]
                # Add new data point
                self.incoming_data = self.incoming_data[1:] + [network_data.get("bytes_recv", 0) / 1024 / 1024]  # Convert to Mbps
                self.outgoing_data = self.outgoing_data[1:] + [network_data.get("bytes_sent", 0) / 1024 / 1024]
            else:
                # Fallback to simulated data
                import random
                self.incoming_data = self.incoming_data[1:] + [random.uniform(10, 100)]
                self.outgoing_data = self.outgoing_data[1:] + [random.uniform(5, 50)]
        else:
            # Simulate data if API fails
            import random
            self.incoming_data = self.incoming_data[1:] + [random.uniform(10, 100)]
            self.outgoing_data = self.outgoing_data[1:] + [random.uniform(5, 50)]
        
        # Update plots
        self.incoming_plot.setData(self.time_data, self.incoming_data)
        self.outgoing_plot.setData(self.time_data, self.outgoing_data)
        
    def update_with_network_data(self, network_data):
        """Update with real-time network data"""
        if isinstance(network_data, dict):
            # Add new data point
            self.incoming_data = self.incoming_data[1:] + [network_data.get("bytes_recv", 0) / 1024 / 1024]
            self.outgoing_data = self.outgoing_data[1:] + [network_data.get("bytes_sent", 0) / 1024 / 1024]
            
            # Update plots
            self.incoming_plot.setData(self.time_data, self.incoming_data)
            self.outgoing_plot.setData(self.time_data, self.outgoing_data)


class ResourceMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # CPU usage
        self.cpu_plot = pg.PlotWidget()
        self.cpu_plot.setLabel('left', 'CPU Usage', units='%')
        self.cpu_plot.setLabel('bottom', 'Device')
        self.cpu_plot.showGrid(True, True)
        self.cpu_plot.setBackground('w')
        
        layout.addWidget(QLabel("CPU Usage by Device"))
        layout.addWidget(self.cpu_plot)
        
        # Memory usage
        self.memory_plot = pg.PlotWidget()
        self.memory_plot.setLabel('left', 'Memory Usage', units='GB')
        self.memory_plot.setLabel('bottom', 'Device')
        self.memory_plot.showGrid(True, True)
        self.memory_plot.setBackground('w')
        
        layout.addWidget(QLabel("Memory Usage by Device"))
        layout.addWidget(self.memory_plot)
        
    def update_data(self):
        # Try to get real data from API
        api_client = get_api_client()
        result = api_client.get_metrics()
        
        if result.get("success") and result.get("data"):
            # Process real metrics
            self._process_metrics(result.get("data", {}))
        else:
            # Simulate resource data
            import random
            
            devices = ['Server-01', 'Server-02', 'Router', 'Workstation-01']
            cpu_data = [random.uniform(20, 80) for _ in devices]
            memory_data = [random.uniform(2, 16) for _ in devices]
            
            # Update bar graphs
            self.cpu_plot.clear()
            self.cpu_plot.plot(x=range(len(devices)), y=cpu_data, pen=None, symbol='o', symbolBrush='b')
            
            self.memory_plot.clear()
            self.memory_plot.plot(x=range(len(devices)), y=memory_data, pen=None, symbol='o', symbolBrush='g')
            
    def _process_metrics(self, metrics_data):
        """Process metrics data from API"""
        devices = []
        cpu_data = []
        memory_data = []
        
        if isinstance(metrics_data, list):
            for metric in metrics_data:
                device_name = metric.get("hostname", metric.get("device_id", "Unknown"))
                devices.append(device_name)
                cpu_data.append(metric.get("cpu_percent", 0))
                memory_data.append(metric.get("memory_used_gb", 0))
        elif isinstance(metrics_data, dict):
            # Single device metrics
            devices = [metrics_data.get("hostname", "Local")]
            cpu_data = [metrics_data.get("cpu_percent", 0)]
            memory_data = [metrics_data.get("memory_used_gb", 0)]
            
        if devices:
            # Update bar graphs
            self.cpu_plot.clear()
            self.cpu_plot.plot(x=range(len(devices)), y=cpu_data, pen=None, symbol='o', symbolBrush='b')
            
            self.memory_plot.clear()
            self.memory_plot.plot(x=range(len(devices)), y=memory_data, pen=None, symbol='o', symbolBrush='g')
            
    def update_with_resource_data(self, resource_data):
        """Update with real-time resource data"""
        self._process_metrics(resource_data)


class AlertsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Alerts list
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        
        self.alerts_list = QListWidget()
        layout.addWidget(self.alerts_list)
        
        # Add some sample alerts
        self.add_alert("High CPU usage on Server-01 (85%)", "warning")
        self.add_alert("Disk space low on Workstation-02 (10% free)", "error")
        self.add_alert("Network latency spike detected (150ms)", "info")
        
    def add_alert(self, message, severity="info"):
        item = QListWidgetItem(message)
        
        if severity == "error":
            item.setBackground(Qt.red)
            item.setForeground(Qt.white)
        elif severity == "warning":
            item.setBackground(Qt.yellow)
        else:
            item.setBackground(Qt.lightGray)
            
        self.alerts_list.addItem(item)
        
    def check_alerts(self):
        # Check for new alerts from API
        api_client = get_api_client()
        # This would fetch alerts from a dedicated endpoint
        # For now, we'll keep the existing sample alerts
        pass
        
    def update_with_alerts(self, alerts_data):
        """Update alerts list with new data"""
        if isinstance(alerts_data, list):
            # Clear existing alerts
            self.alerts_list.clear()
            
            # Add new alerts
            for alert in alerts_data:
                message = alert.get("message", "Unknown alert")
                severity = alert.get("severity", "info")
                self.add_alert(message, severity)