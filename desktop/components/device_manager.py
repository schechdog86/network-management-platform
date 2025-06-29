"""
Device Manager Widget - Manage network devices
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QTableWidget, QTableWidgetItem, QPushButton,
                               QLineEdit, QComboBox, QLabel, QMenu,
                               QHeaderView)
from PySide6.QtCore import Qt, Signal, Slot, QPoint
from PySide6.QtGui import QAction

class DeviceManagerWidget(QWidget):
    device_selected = Signal(str)
    device_action = Signal(str, str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
        self.load_devices()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Search and filter bar
        filter_layout = QHBoxLayout()
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search devices...")
        self.search_box.textChanged.connect(self.filter_devices)
        filter_layout.addWidget(self.search_box)
        
        # Type filter
        filter_layout.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Server", "Workstation", "Network", "Printer", "Other"])
        self.type_filter.currentTextChanged.connect(self.filter_devices)
        filter_layout.addWidget(self.type_filter)
        
        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Online", "Offline", "Warning"])
        self.status_filter.currentTextChanged.connect(self.filter_devices)
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addStretch()
        
        # Add device button
        add_device_btn = QPushButton("Add Device")
        add_device_btn.clicked.connect(self.add_device)
        filter_layout.addWidget(add_device_btn)
        
        layout.addLayout(filter_layout)
        
        # Device table
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(6)
        self.device_table.setHorizontalHeaderLabels([
            "Name", "IP Address", "MAC Address", "Type", "Status", "Last Seen"
        ])
        
        # Configure table
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.horizontalHeader().setStretchLastSection(True)
        self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        
        # Context menu
        self.device_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.device_table.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.device_table)
        
    def load_devices(self):
        # Sample devices
        devices = [
            ["Router", "192.168.1.1", "00:11:22:33:44:55", "Network", "Online", "Just now"],
            ["Server-01", "192.168.1.10", "00:11:22:33:44:56", "Server", "Online", "2 mins ago"],
            ["Server-02", "192.168.1.11", "00:11:22:33:44:57", "Server", "Online", "1 min ago"],
            ["Workstation-01", "192.168.1.100", "00:11:22:33:44:58", "Workstation", "Online", "5 mins ago"],
            ["Workstation-02", "192.168.1.101", "00:11:22:33:44:59", "Workstation", "Offline", "2 hours ago"],
            ["Printer-01", "192.168.1.150", "00:11:22:33:44:60", "Printer", "Offline", "1 day ago"],
        ]
        
        self.device_table.setRowCount(len(devices))
        
        for row, device in enumerate(devices):
            for col, value in enumerate(device):
                item = QTableWidgetItem(value)
                if col == 4:  # Status column
                    if value == "Online":
                        item.setBackground(Qt.green)
                    elif value == "Offline":
                        item.setBackground(Qt.red)
                        item.setForeground(Qt.white)
                self.device_table.setItem(row, col, item)
                
    @Slot(str)
    def filter_devices(self, text=""):
        search_text = self.search_box.text().lower()
        type_filter = self.type_filter.currentText()
        status_filter = self.status_filter.currentText()
        
        for row in range(self.device_table.rowCount()):
            show_row = True
            
            # Search filter
            if search_text:
                found = False
                for col in range(self.device_table.columnCount()):
                    item = self.device_table.item(row, col)
                    if item and search_text in item.text().lower():
                        found = True
                        break
                if not found:
                    show_row = False
                    
            # Type filter
            if show_row and type_filter != "All":
                type_item = self.device_table.item(row, 3)
                if type_item and type_item.text() != type_filter:
                    show_row = False
                    
            # Status filter
            if show_row and status_filter != "All":
                status_item = self.device_table.item(row, 4)
                if status_item and status_item.text() != status_filter:
                    show_row = False
                    
            self.device_table.setRowHidden(row, not show_row)
            
    @Slot(QPoint)
    def show_context_menu(self, position):
        menu = QMenu()
        
        # Get selected device
        current_row = self.device_table.currentRow()
        if current_row < 0:
            return
            
        device_name = self.device_table.item(current_row, 0).text()
        
        # Actions
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(lambda: self.device_action.emit(device_name, "connect"))
        menu.addAction(connect_action)
        
        reboot_action = QAction("Reboot", self)
        reboot_action.triggered.connect(lambda: self.device_action.emit(device_name, "reboot"))
        menu.addAction(reboot_action)
        
        menu.addSeparator()
        
        properties_action = QAction("Properties", self)
        properties_action.triggered.connect(lambda: self.show_device_properties(device_name))
        menu.addAction(properties_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.remove_device(current_row))
        menu.addAction(remove_action)
        
        menu.exec(self.device_table.mapToGlobal(position))
        
    @Slot()
    def add_device(self):
        # Placeholder for add device dialog
        pass
        
    @Slot(int)
    def remove_device(self, row):
        self.device_table.removeRow(row)
        
    @Slot(str)
    def show_device_properties(self, device_name):
        self.device_selected.emit(device_name)
        
    def refresh(self):
        # Reload devices from backend
        self.load_devices()