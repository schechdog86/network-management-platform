"""
Backup Manager Widget - Manage system backups
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QTableWidget, QTableWidgetItem, QPushButton,
                               QProgressBar, QLabel, QGroupBox, QComboBox,
                               QCheckBox, QSpinBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from datetime import datetime

class BackupManagerWidget(QWidget):
    backup_started = Signal(str)
    backup_completed = Signal(str, bool)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
        self.load_backup_history()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Backup controls
        controls_group = QGroupBox("Backup Controls")
        controls_layout = QVBoxLayout()
        
        # Backup type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Backup Type:"))
        self.backup_type = QComboBox()
        self.backup_type.addItems(["Full System", "Configuration Only", "User Data", "Custom"])
        type_layout.addWidget(self.backup_type)
        type_layout.addStretch()
        controls_layout.addLayout(type_layout)
        
        # Options
        options_layout = QHBoxLayout()
        self.compress_check = QCheckBox("Compress")
        self.compress_check.setChecked(True)
        options_layout.addWidget(self.compress_check)
        
        self.encrypt_check = QCheckBox("Encrypt")
        self.encrypt_check.setChecked(True)
        options_layout.addWidget(self.encrypt_check)
        
        self.verify_check = QCheckBox("Verify after backup")
        self.verify_check.setChecked(True)
        options_layout.addWidget(self.verify_check)
        
        options_layout.addStretch()
        controls_layout.addLayout(options_layout)
        
        # Retention policy
        retention_layout = QHBoxLayout()
        retention_layout.addWidget(QLabel("Keep backups for:"))
        self.retention_days = QSpinBox()
        self.retention_days.setMinimum(1)
        self.retention_days.setMaximum(365)
        self.retention_days.setValue(30)
        retention_layout.addWidget(self.retention_days)
        retention_layout.addWidget(QLabel("days"))
        retention_layout.addStretch()
        controls_layout.addLayout(retention_layout)
        
        # Backup button and progress
        button_layout = QHBoxLayout()
        self.backup_button = QPushButton("Start Backup")
        self.backup_button.clicked.connect(self.start_backup)
        button_layout.addWidget(self.backup_button)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        button_layout.addWidget(self.progress_bar)
        
        controls_layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("Ready")
        controls_layout.addWidget(self.status_label)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Backup history
        history_group = QGroupBox("Backup History")
        history_layout = QVBoxLayout()
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Type", "Size", "Duration", "Status"
        ])
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        history_layout.addWidget(self.history_table)
        
        # History controls
        history_controls = QHBoxLayout()
        restore_btn = QPushButton("Restore Selected")
        restore_btn.clicked.connect(self.restore_backup)
        history_controls.addWidget(restore_btn)
        
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_backup)
        history_controls.addWidget(delete_btn)
        
        history_controls.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_backup_history)
        history_controls.addWidget(refresh_btn)
        
        history_layout.addLayout(history_controls)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
    def load_backup_history(self):
        # Sample backup history
        backups = [
            [datetime.now().strftime("%Y-%m-%d %H:%M"), "Full System", "45.2 GB", "2h 15m", "Success"],
            [(datetime.now()).strftime("%Y-%m-%d %H:%M"), "Configuration", "125 MB", "2m 30s", "Success"],
            [(datetime.now()).strftime("%Y-%m-%d %H:%M"), "User Data", "12.8 GB", "45m", "Success"],
            [(datetime.now()).strftime("%Y-%m-%d %H:%M"), "Full System", "44.9 GB", "2h 10m", "Failed"],
        ]
        
        self.history_table.setRowCount(len(backups))
        
        for row, backup in enumerate(backups):
            for col, value in enumerate(backup):
                item = QTableWidgetItem(value)
                if col == 4:  # Status column
                    if value == "Success":
                        item.setBackground(Qt.green)
                    elif value == "Failed":
                        item.setBackground(Qt.red)
                        item.setForeground(Qt.white)
                self.history_table.setItem(row, col, item)
                
    @Slot()
    def start_backup(self):
        backup_type = self.backup_type.currentText()
        self.backup_started.emit(backup_type)
        
        # Disable controls
        self.backup_button.setEnabled(False)
        self.backup_type.setEnabled(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.status_label.setText(f"Starting {backup_type} backup...")
        
        # Simulate backup progress
        self.backup_timer = QTimer()
        self.backup_progress = 0
        self.backup_timer.timeout.connect(self.update_progress)
        self.backup_timer.start(100)
        
    @Slot()
    def update_progress(self):
        self.backup_progress += 2
        self.progress_bar.setValue(self.backup_progress)
        
        if self.backup_progress >= 100:
            self.backup_timer.stop()
            self.complete_backup()
            
    def complete_backup(self):
        # Re-enable controls
        self.backup_button.setEnabled(True)
        self.backup_type.setEnabled(True)
        
        # Hide progress
        self.progress_bar.setVisible(False)
        
        # Update status
        self.status_label.setText("Backup completed successfully")
        
        # Add to history
        new_backup = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            self.backup_type.currentText(),
            "15.3 GB",
            "35m",
            "Success"
        ]
        
        row_count = self.history_table.rowCount()
        self.history_table.insertRow(0)
        
        for col, value in enumerate(new_backup):
            item = QTableWidgetItem(value)
            if col == 4:
                item.setBackground(Qt.green)
            self.history_table.setItem(0, col, item)
            
        self.backup_completed.emit(self.backup_type.currentText(), True)
        
    @Slot()
    def restore_backup(self):
        current_row = self.history_table.currentRow()
        if current_row >= 0:
            backup_date = self.history_table.item(current_row, 0).text()
            self.status_label.setText(f"Restoring backup from {backup_date}...")
            
    @Slot()
    def delete_backup(self):
        current_row = self.history_table.currentRow()
        if current_row >= 0:
            self.history_table.removeRow(current_row)
            self.status_label.setText("Backup deleted")
            
    def refresh(self):
        self.load_backup_history()