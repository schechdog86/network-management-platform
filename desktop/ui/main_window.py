"""
Main Window for Network Management Desktop Application
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QTabWidget, QMenuBar, 
                               QStatusBar, QToolBar, QMessageBox,
                               QDialog, QFormLayout, QLineEdit, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QAction

from desktop.components.network_overview import NetworkOverviewWidget
from desktop.components.device_manager import DeviceManagerWidget
from desktop.components.monitoring import MonitoringWidget
from desktop.components.backup_manager import BackupManagerWidget
from desktop.components.ai_assistant import AIAssistantWidget
from desktop.components.settings import SettingsWidget
from desktop.components.real_time_dashboard import RealTimeDashboard
from desktop.utils.api_client import get_api_client
from desktop.utils.theme_manager import get_theme_manager

class MainWindow(QMainWindow):
    # Signals
    status_message = Signal(str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.api_client = get_api_client(config.get("api.base_url"))
        self.theme_manager = get_theme_manager()
        self.connection_status = False
        
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        self.connect_signals()
        self.apply_theme()
        self.check_backend_connection()
        
    def setup_ui(self):
        self.setWindowTitle("Network Manager")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Add tabs
        self.real_time_dashboard = RealTimeDashboard(self.config)
        self.tabs.addTab(self.real_time_dashboard, "Dashboard")
        
        self.network_overview = NetworkOverviewWidget(self.config)
        self.tabs.addTab(self.network_overview, "Network Overview")
        
        self.device_manager = DeviceManagerWidget(self.config)
        self.tabs.addTab(self.device_manager, "Devices")
        
        self.monitoring = MonitoringWidget(self.config)
        self.tabs.addTab(self.monitoring, "Monitoring")
        
        self.backup_manager = BackupManagerWidget(self.config)
        self.tabs.addTab(self.backup_manager, "Backups")
        
        self.ai_assistant = AIAssistantWidget(self.config)
        self.tabs.addTab(self.ai_assistant, "AI Assistant")
        
        self.settings = SettingsWidget(self.config)
        self.tabs.addTab(self.settings, "Settings")
        
    def setup_menus(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Login action
        login_action = QAction("&Login...", self)
        login_action.triggered.connect(self.show_login_dialog)
        file_menu.addAction(login_action)
        
        file_menu.addSeparator()
        
        # Refresh action
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self.refresh_current_tab)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        # Network scan
        scan_action = QAction("&Network Scan", self)
        scan_action.triggered.connect(self.perform_network_scan)
        tools_menu.addAction(scan_action)
        
        # Backup now
        backup_action = QAction("&Backup Now", self)
        backup_action.triggered.connect(self.perform_backup)
        tools_menu.addAction(backup_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Toggle toolbar
        toggle_toolbar = QAction("&Toolbar", self)
        toggle_toolbar.setCheckable(True)
        toggle_toolbar.setChecked(True)
        toggle_toolbar.triggered.connect(self.toggle_toolbar)
        view_menu.addAction(toggle_toolbar)
        
        view_menu.addSeparator()
        
        # Theme submenu
        theme_menu = view_menu.addMenu("&Theme")
        
        # Light theme
        light_theme_action = QAction("&Light", self)
        light_theme_action.setCheckable(True)
        light_theme_action.triggered.connect(lambda: self.change_theme("light"))
        theme_menu.addAction(light_theme_action)
        
        # Dark theme
        dark_theme_action = QAction("&Dark", self)
        dark_theme_action.setCheckable(True)
        dark_theme_action.triggered.connect(lambda: self.change_theme("dark"))
        theme_menu.addAction(dark_theme_action)
        
        # System theme
        system_theme_action = QAction("&System", self)
        system_theme_action.setCheckable(True)
        system_theme_action.triggered.connect(lambda: self.change_theme("system"))
        theme_menu.addAction(system_theme_action)
        
        # Theme action group
        self.theme_actions = {
            "light": light_theme_action,
            "dark": dark_theme_action,
            "system": system_theme_action
        }
        
        # Update checked state
        current_theme = self.theme_manager.get_current_theme()
        if current_theme in self.theme_actions:
            self.theme_actions[current_theme].setChecked(True)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        # About
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def setup_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        
        # Refresh
        refresh_action = QAction("Refresh", self)
        refresh_action.setToolTip("Refresh current view")
        refresh_action.triggered.connect(self.refresh_current_tab)
        self.toolbar.addAction(refresh_action)
        
        self.toolbar.addSeparator()
        
        # Network scan
        scan_action = QAction("Scan", self)
        scan_action.setToolTip("Perform network scan")
        scan_action.triggered.connect(self.perform_network_scan)
        self.toolbar.addAction(scan_action)
        
        # Backup
        backup_action = QAction("Backup", self)
        backup_action.setToolTip("Start backup process")
        backup_action.triggered.connect(self.perform_backup)
        self.toolbar.addAction(backup_action)
        
    def setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")
        
    def connect_signals(self):
        # Connect status messages from widgets
        self.status_message.connect(self.update_status)
        
    @Slot()
    def refresh_current_tab(self):
        current_widget = self.tabs.currentWidget()
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()
            self.update_status("Refreshed")
            
    @Slot()
    def perform_network_scan(self):
        self.update_status("Starting network scan...")
        # Switch to network overview tab
        self.tabs.setCurrentWidget(self.network_overview)
        self.network_overview.start_scan()
        
    @Slot()
    def perform_backup(self):
        self.update_status("Starting backup process...")
        # Switch to backup tab
        self.tabs.setCurrentWidget(self.backup_manager)
        self.backup_manager.start_backup()
        
    @Slot()
    def toggle_toolbar(self, checked):
        self.toolbar.setVisible(checked)
        
    @Slot(str)
    def update_status(self, message):
        self.statusbar.showMessage(message, 5000)  # Show for 5 seconds
        
    @Slot()
    def show_about(self):
        QMessageBox.about(self, "About Network Manager",
                          "Network Manager v0.1.0\n\n"
                          "A comprehensive network management solution\n"
                          "for monitoring, administration, and automation.")
        
    def closeEvent(self, event):
        # Confirm exit
        reply = QMessageBox.question(self, "Confirm Exit",
                                     "Are you sure you want to exit?",
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Disconnect WebSocket if connected
            if hasattr(self.api_client, 'disconnect_websocket'):
                self.api_client.disconnect_websocket()
            event.accept()
        else:
            event.ignore()
            
    def apply_theme(self):
        """Apply the current theme"""
        self.theme_manager.apply_theme()
        
    @Slot(str)
    def change_theme(self, theme_name):
        """Change application theme"""
        self.theme_manager.apply_theme(theme_name)
        # Update checked states
        for name, action in self.theme_actions.items():
            action.setChecked(name == theme_name)
        self.update_status(f"Theme changed to {theme_name}")
        
    def check_backend_connection(self):
        """Check connection to backend API"""
        try:
            result = self.api_client.get_network_status()
            if result.get("success"):
                self.connection_status = True
                self.update_status("Connected to backend")
                self.setup_websocket()
                # Auto-login if credentials are saved
                self.auto_login()
            else:
                self.connection_status = False
                self.update_status("Backend connection failed - running in offline mode")
        except Exception as e:
            self.connection_status = False
            self.update_status(f"Backend not available: {str(e)}")
            
    def setup_websocket(self):
        """Setup WebSocket connection for real-time updates"""
        if self.connection_status:
            self.api_client.connect_websocket()
            self.api_client.data_received.connect(self.handle_websocket_data)
            self.api_client.connection_status_changed.connect(self.handle_websocket_status)
            
    @Slot(dict)
    def handle_websocket_data(self, data):
        """Handle incoming WebSocket data"""
        # Route data to appropriate widgets
        if data.get("type") == "metrics":
            self.monitoring.update_with_data(data.get("data", {}))
            self.real_time_dashboard.update_from_websocket(data.get("data", {}))
        elif data.get("type") == "device_status":
            self.network_overview.update_device_status(data.get("data", {}))
        elif data.get("type") == "alert":
            self.show_alert(data.get("message", ""))
            
    @Slot(bool)
    def handle_websocket_status(self, connected):
        """Handle WebSocket connection status change"""
        if connected:
            self.update_status("Real-time updates connected")
        else:
            self.update_status("Real-time updates disconnected")
            
    def show_alert(self, message):
        """Show alert notification"""
        QMessageBox.warning(self, "Alert", message)
        
    def auto_login(self):
        """Attempt auto-login with saved credentials"""
        # This would check for saved credentials in secure storage
        # For now, we'll skip auto-login
        pass
        
    def show_login_dialog(self):
        """Show login dialog"""
        dialog = LoginDialog(self)
        if dialog.exec() == QDialog.Accepted:
            username = dialog.username_input.text()
            password = dialog.password_input.text()
            
            result = self.api_client.login(username, password)
            if result.get("success"):
                self.update_status("Login successful")
                self.refresh_all_widgets()
            else:
                QMessageBox.critical(self, "Login Failed", 
                                   result.get("error", "Unknown error"))
                
    def refresh_all_widgets(self):
        """Refresh all widget data"""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'refresh'):
                widget.refresh()


class LoginDialog(QDialog):
    """Simple login dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setModal(True)
        
        layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password")
        layout.addRow("Password:", self.password_input)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)