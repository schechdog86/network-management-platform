"""
Settings Widget - Application configuration
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QTabWidget, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QCheckBox, QComboBox, QGroupBox,
                               QFormLayout, QTextEdit, QFileDialog)
from PySide6.QtCore import Qt, Signal, Slot

class SettingsWidget(QWidget):
    settings_changed = Signal(str, object)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Settings tabs
        self.tabs = QTabWidget()
        
        # General settings
        self.general_tab = self.create_general_tab()
        self.tabs.addTab(self.general_tab, "General")
        
        # Network settings
        self.network_tab = self.create_network_tab()
        self.tabs.addTab(self.network_tab, "Network")
        
        # Monitoring settings
        self.monitoring_tab = self.create_monitoring_tab()
        self.tabs.addTab(self.monitoring_tab, "Monitoring")
        
        # Backup settings
        self.backup_tab = self.create_backup_tab()
        self.tabs.addTab(self.backup_tab, "Backup")
        
        # AI settings
        self.ai_tab = self.create_ai_tab()
        self.tabs.addTab(self.ai_tab, "AI Assistant")
        
        layout.addWidget(self.tabs)
        
        # Save/Cancel buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(save_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.load_settings)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
    def create_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # API settings
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout()
        
        self.api_url = QLineEdit()
        api_layout.addRow("API URL:", self.api_url)
        
        self.api_timeout = QSpinBox()
        self.api_timeout.setMinimum(5)
        self.api_timeout.setMaximum(300)
        self.api_timeout.setSuffix(" seconds")
        api_layout.addRow("Timeout:", self.api_timeout)
        
        self.verify_ssl = QCheckBox("Verify SSL certificates")
        api_layout.addRow("Security:", self.verify_ssl)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # UI settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Default", "Dark", "Light"])
        ui_layout.addRow("Theme:", self.theme_combo)
        
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setMinimum(1)
        self.refresh_interval.setMaximum(60)
        self.refresh_interval.setSuffix(" seconds")
        ui_layout.addRow("Auto-refresh:", self.refresh_interval)
        
        self.notifications_enabled = QCheckBox("Enable notifications")
        ui_layout.addRow("Notifications:", self.notifications_enabled)
        
        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)
        
        layout.addStretch()
        return widget
        
    def create_network_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Scan settings
        scan_group = QGroupBox("Network Scanning")
        scan_layout = QFormLayout()
        
        self.scan_interval = QSpinBox()
        self.scan_interval.setMinimum(60)
        self.scan_interval.setMaximum(3600)
        self.scan_interval.setSuffix(" seconds")
        scan_layout.addRow("Scan interval:", self.scan_interval)
        
        self.max_concurrent_scans = QSpinBox()
        self.max_concurrent_scans.setMinimum(1)
        self.max_concurrent_scans.setMaximum(20)
        scan_layout.addRow("Concurrent scans:", self.max_concurrent_scans)
        
        self.scan_timeout = QSpinBox()
        self.scan_timeout.setMinimum(1)
        self.scan_timeout.setMaximum(60)
        self.scan_timeout.setSuffix(" seconds")
        scan_layout.addRow("Scan timeout:", self.scan_timeout)
        
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)
        
        layout.addStretch()
        return widget
        
    def create_monitoring_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Monitoring settings
        monitor_group = QGroupBox("Monitoring Configuration")
        monitor_layout = QFormLayout()
        
        self.monitor_interval = QSpinBox()
        self.monitor_interval.setMinimum(10)
        self.monitor_interval.setMaximum(600)
        self.monitor_interval.setSuffix(" seconds")
        monitor_layout.addRow("Update interval:", self.monitor_interval)
        
        self.retention_days = QSpinBox()
        self.retention_days.setMinimum(1)
        self.retention_days.setMaximum(365)
        self.retention_days.setSuffix(" days")
        monitor_layout.addRow("Data retention:", self.retention_days)
        
        self.alert_threshold = QSpinBox()
        self.alert_threshold.setMinimum(50)
        self.alert_threshold.setMaximum(100)
        self.alert_threshold.setSuffix("%")
        monitor_layout.addRow("Alert threshold:", self.alert_threshold)
        
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)
        
        layout.addStretch()
        return widget
        
    def create_backup_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Backup settings
        backup_group = QGroupBox("Backup Configuration")
        backup_layout = QFormLayout()
        
        # Backup location
        location_layout = QHBoxLayout()
        self.backup_location = QLineEdit()
        location_layout.addWidget(self.backup_location)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_backup_location)
        location_layout.addWidget(browse_button)
        
        backup_layout.addRow("Backup location:", location_layout)
        
        self.backup_compression = QCheckBox("Enable compression")
        backup_layout.addRow("Compression:", self.backup_compression)
        
        self.backup_encryption = QCheckBox("Enable encryption")
        backup_layout.addRow("Encryption:", self.backup_encryption)
        
        self.backup_retention = QSpinBox()
        self.backup_retention.setMinimum(1)
        self.backup_retention.setMaximum(365)
        self.backup_retention.setSuffix(" days")
        backup_layout.addRow("Retention period:", self.backup_retention)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        layout.addStretch()
        return widget
        
    def create_ai_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # AI settings
        ai_group = QGroupBox("AI Assistant Configuration")
        ai_layout = QFormLayout()
        
        self.ai_enabled = QCheckBox("Enable AI assistant")
        ai_layout.addRow("Status:", self.ai_enabled)
        
        self.ai_model = QComboBox()
        self.ai_model.addItems(["gpt-3.5-turbo", "gpt-4", "claude-2", "llama-2"])
        ai_layout.addRow("Model:", self.ai_model)
        
        self.max_tokens = QSpinBox()
        self.max_tokens.setMinimum(100)
        self.max_tokens.setMaximum(4000)
        self.max_tokens.setSingleStep(100)
        ai_layout.addRow("Max tokens:", self.max_tokens)
        
        self.temperature = QSpinBox()
        self.temperature.setMinimum(0)
        self.temperature.setMaximum(100)
        self.temperature.setSuffix("%")
        ai_layout.addRow("Temperature:", self.temperature)
        
        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)
        
        # API key
        api_key_group = QGroupBox("API Configuration")
        api_key_layout = QFormLayout()
        
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        api_key_layout.addRow("API Key:", self.api_key)
        
        api_key_group.setLayout(api_key_layout)
        layout.addWidget(api_key_group)
        
        layout.addStretch()
        return widget
        
    @Slot()
    def browse_backup_location(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Backup Directory",
            self.backup_location.text()
        )
        if directory:
            self.backup_location.setText(directory)
            
    def load_settings(self):
        # General settings
        self.api_url.setText(self.config.get("api.base_url", ""))
        self.api_timeout.setValue(self.config.get("api.timeout", 30))
        self.verify_ssl.setChecked(self.config.get("api.verify_ssl", True))
        
        self.theme_combo.setCurrentText(self.config.get("ui.theme", "Default"))
        self.refresh_interval.setValue(self.config.get("ui.refresh_interval", 5))
        self.notifications_enabled.setChecked(self.config.get("ui.notifications_enabled", True))
        
        # Network settings
        self.scan_interval.setValue(self.config.get("network.scan_interval", 300))
        self.max_concurrent_scans.setValue(self.config.get("network.max_concurrent_scans", 5))
        self.scan_timeout.setValue(self.config.get("network.timeout", 10))
        
        # Monitoring settings
        self.monitor_interval.setValue(self.config.get("monitoring.update_interval", 60))
        self.retention_days.setValue(self.config.get("monitoring.retention_days", 30))
        self.alert_threshold.setValue(int(self.config.get("monitoring.alert_threshold", 0.8) * 100))
        
        # Backup settings
        self.backup_location.setText(self.config.get("backup.default_location", ""))
        self.backup_compression.setChecked(self.config.get("backup.compression", True))
        self.backup_encryption.setChecked(self.config.get("backup.encryption", True))
        self.backup_retention.setValue(self.config.get("backup.retention_days", 90))
        
        # AI settings
        self.ai_enabled.setChecked(self.config.get("ai.enabled", True))
        self.ai_model.setCurrentText(self.config.get("ai.model", "gpt-3.5-turbo"))
        self.max_tokens.setValue(self.config.get("ai.max_tokens", 2000))
        self.temperature.setValue(int(self.config.get("ai.temperature", 0.7) * 100))
        
    @Slot()
    def save_settings(self):
        # General settings
        self.config.set("api.base_url", self.api_url.text())
        self.config.set("api.timeout", self.api_timeout.value())
        self.config.set("api.verify_ssl", self.verify_ssl.isChecked())
        
        self.config.set("ui.theme", self.theme_combo.currentText())
        self.config.set("ui.refresh_interval", self.refresh_interval.value())
        self.config.set("ui.notifications_enabled", self.notifications_enabled.isChecked())
        
        # Network settings
        self.config.set("network.scan_interval", self.scan_interval.value())
        self.config.set("network.max_concurrent_scans", self.max_concurrent_scans.value())
        self.config.set("network.timeout", self.scan_timeout.value())
        
        # Monitoring settings
        self.config.set("monitoring.update_interval", self.monitor_interval.value())
        self.config.set("monitoring.retention_days", self.retention_days.value())
        self.config.set("monitoring.alert_threshold", self.alert_threshold.value() / 100.0)
        
        # Backup settings
        self.config.set("backup.default_location", self.backup_location.text())
        self.config.set("backup.compression", self.backup_compression.isChecked())
        self.config.set("backup.encryption", self.backup_encryption.isChecked())
        self.config.set("backup.retention_days", self.backup_retention.value())
        
        # AI settings
        self.config.set("ai.enabled", self.ai_enabled.isChecked())
        self.config.set("ai.model", self.ai_model.currentText())
        self.config.set("ai.max_tokens", self.max_tokens.value())
        self.config.set("ai.temperature", self.temperature.value() / 100.0)
        
        # Save to file
        self.config.save()
        self.settings_changed.emit("all", self.config.config)
        
    def refresh(self):
        self.load_settings()