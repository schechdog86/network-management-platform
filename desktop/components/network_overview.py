"""
Network Overview Widget - Main dashboard view
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QTreeWidget, 
                               QTreeWidgetItem, QGroupBox, QGridLayout,
                               QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QFont
from desktop.utils.api_client import get_api_client
import json

class NetworkOverviewWidget(QWidget):
    scan_started = Signal()
    scan_completed = Signal(list)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
        self.setup_timer()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Network Overview")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        scan_btn = QPushButton("Scan Network")
        scan_btn.clicked.connect(self.start_scan)
        header_layout.addWidget(scan_btn)
        
        layout.addLayout(header_layout)
        
        # Statistics
        stats_group = QGroupBox("Network Statistics")
        stats_layout = QGridLayout()
        
        # Total devices
        stats_layout.addWidget(QLabel("Total Devices:"), 0, 0)
        self.total_devices_label = QLabel("0")
        self.total_devices_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.total_devices_label, 0, 1)
        
        # Online devices
        stats_layout.addWidget(QLabel("Online:"), 0, 2)
        self.online_devices_label = QLabel("0")
        self.online_devices_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.online_devices_label, 0, 3)
        
        # Offline devices
        stats_layout.addWidget(QLabel("Offline:"), 1, 0)
        self.offline_devices_label = QLabel("0")
        self.offline_devices_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.offline_devices_label, 1, 1)
        
        # Warnings
        stats_layout.addWidget(QLabel("Warnings:"), 1, 2)
        self.warnings_label = QLabel("0")
        self.warnings_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.warnings_label, 1, 3)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Device tree
        self.device_tree = QTreeWidget()
        self.device_tree.setHeaderLabels(["Device", "IP Address", "Status", "Type"])
        self.device_tree.setAlternatingRowColors(True)
        layout.addWidget(self.device_tree)
        
    def setup_timer(self):
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        interval = self.config.get("ui.refresh_interval", 5) * 1000
        self.refresh_timer.start(interval)
        
    @Slot()
    def start_scan(self):
        self.scan_started.emit()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Use API to scan network
        api_client = get_api_client(self.config.get("api.base_url"))
        result = api_client.scan_network()
        
        if result.get("success"):
            # Get devices after scan
            QTimer.singleShot(2000, self.fetch_devices)
        else:
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Scan Failed", 
                              result.get("error", "Failed to scan network"))
        
    @Slot()
    def fetch_devices(self):
        """Fetch devices from API"""
        api_client = get_api_client(self.config.get("api.base_url"))
        result = api_client.get_devices()
        
        self.progress_bar.setVisible(False)
        
        if result.get("success"):
            devices = result.get("data", [])
            # Transform API data to expected format
            formatted_devices = []
            for device in devices:
                formatted_devices.append({
                    "name": device.get("hostname", device.get("ip_address", "Unknown")),
                    "ip": device.get("ip_address", "N/A"),
                    "status": "Online" if device.get("is_online", False) else "Offline",
                    "type": device.get("device_type", "Unknown").title()
                })
            
            self.update_device_list(formatted_devices)
            self.scan_completed.emit(formatted_devices)
        else:
            # Fall back to simulated data if API fails
            devices = [
                {"name": "Router", "ip": "192.168.1.1", "status": "Online", "type": "Network"},
                {"name": "Server-01", "ip": "192.168.1.10", "status": "Online", "type": "Server"},
                {"name": "Workstation-01", "ip": "192.168.1.100", "status": "Online", "type": "Workstation"},
                {"name": "Printer-01", "ip": "192.168.1.150", "status": "Offline", "type": "Printer"},
            ]
            self.update_device_list(devices)
            self.scan_completed.emit(devices)
        
    def update_device_list(self, devices):
        self.device_tree.clear()
        
        online = 0
        offline = 0
        
        for device in devices:
            item = QTreeWidgetItem([
                device["name"],
                device["ip"],
                device["status"],
                device["type"]
            ])
            
            if device["status"] == "Online":
                online += 1
            else:
                offline += 1
                # Highlight offline devices
                for i in range(4):
                    item.setBackground(i, Qt.lightGray)
                    
            self.device_tree.addTopLevelItem(item)
            
        # Update statistics
        self.total_devices_label.setText(str(len(devices)))
        self.online_devices_label.setText(str(online))
        self.offline_devices_label.setText(str(offline))
        self.warnings_label.setText("0")
        
    @Slot()
    def refresh(self):
        """Refresh device list from API"""
        self.fetch_devices()
        
    def update_device_status(self, status_data):
        """Update device status from WebSocket data"""
        if not isinstance(status_data, dict):
            return
            
        # Update tree widget items based on status data
        for i in range(self.device_tree.topLevelItemCount()):
            item = self.device_tree.topLevelItem(i)
            device_ip = item.text(1)  # IP address column
            
            if device_ip in status_data:
                device_info = status_data[device_ip]
                # Update status column
                new_status = "Online" if device_info.get("is_online", False) else "Offline"
                item.setText(2, new_status)
                
                # Update visual styling
                if new_status == "Offline":
                    for col in range(4):
                        item.setBackground(col, Qt.lightGray)
                else:
                    for col in range(4):
                        item.setBackground(col, Qt.transparent)