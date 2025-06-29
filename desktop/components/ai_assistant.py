"""
AI Assistant Widget - Natural language interface for network management
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QTextEdit, QLineEdit, QPushButton,
                               QLabel, QGroupBox, QListWidget,
                               QSplitter, QProgressBar)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QTextCursor, QFont
import requests
# Lazy imports to avoid initialization issues
# from ai.nlp.command_processor import CommandProcessor
# from ai.orchestrator import AIOrchestrator

class AIWorkerThread(QThread):
    """Worker thread for AI processing to avoid blocking UI"""
    response_ready = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, command, api_url):
        super().__init__()
        self.command = command
        self.api_url = api_url
        
    def run(self):
        try:
            # Try to connect to backend API first
            response = requests.post(
                f"{self.api_url}/api/v1/ai/process-command",
                json={"command": self.command},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.response_ready.emit(result.get("response", "Command processed successfully."))
            else:
                # Fallback to local processing
                self._process_locally()
                
        except Exception as e:
            # Fallback to local processing on error
            self._process_locally()
            
    def _process_locally(self):
        """Process command locally when backend is unavailable"""
        try:
            # Import AI components only when needed to avoid initialization issues
            from ai.nlp.command_processor import CommandProcessor
            from ai.orchestrator import AIOrchestrator
            
            # Initialize local AI components
            command_processor = CommandProcessor()
            ai_orchestrator = AIOrchestrator()
            
            # Process the command
            result = command_processor.process_command(self.command)
            
            if result.get("success"):
                response = result.get("response", "Command processed successfully.")
                self.response_ready.emit(response)
            else:
                self.error_occurred.emit(f"Failed to process command: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self.error_occurred.emit(f"Error processing command locally: {str(e)}")

class AIAssistantWidget(QWidget):
    command_sent = Signal(str)
    response_received = Signal(str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.api_url = config.get("api_url", "http://localhost:8000")
        self.worker_thread = None
        self.setup_ui()
        self.add_welcome_message()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create splitter for chat and suggestions
        splitter = QSplitter(Qt.Horizontal)
        
        # Chat area
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)
        
        # Progress bar for AI processing
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        chat_layout.addWidget(self.progress_bar)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask me anything about your network...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        chat_layout.addLayout(input_layout)
        
        splitter.addWidget(chat_widget)
        
        # Suggestions panel
        suggestions_widget = QWidget()
        suggestions_layout = QVBoxLayout(suggestions_widget)
        
        suggestions_label = QLabel("Suggested Commands")
        suggestions_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        suggestions_label.setFont(font)
        suggestions_layout.addWidget(suggestions_label)
        
        self.suggestions_list = QListWidget()
        self.suggestions_list.itemClicked.connect(self.use_suggestion)
        suggestions_layout.addWidget(self.suggestions_list)
        
        # Add suggestions with modern AI capabilities
        suggestions = [
            "Show me all online devices",
            "Check server health status", 
            "Start a full system backup",
            "Scan the network for new devices",
            "Show CPU usage for all servers",
            "Analyze predictive maintenance recommendations",
            "Check disk space on servers",
            "Show network bandwidth usage",
            "Generate system health report",
            "Schedule maintenance for low-health devices",
            "Show anomaly detection results",
            "Predict when devices might fail"
        ]
        
        self.suggestions_list.addItems(suggestions)
        
        splitter.addWidget(suggestions_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
    def add_welcome_message(self):
        welcome = """<b>AI Network Assistant</b><br>
        <i>I'm here to help you manage your network using natural language commands powered by advanced AI.</i><br><br>
        
        You can ask me to:
        <ul>
        <li>Monitor device status and performance with real-time analytics</li>
        <li>Execute network scans and diagnostics</li>
        <li>Manage backups and configurations</li>
        <li>Perform predictive maintenance analysis</li>
        <li>Detect anomalies and predict failures</li>
        <li>Generate intelligent reports and insights</li>
        <li>Schedule optimized maintenance windows</li>
        </ul>
        
        <b>Features:</b>
        <ul>
        <li>🤖 Natural Language Processing with LangChain</li>
        <li>🔮 Predictive Maintenance with ML</li>
        <li>⚡ Real-time Health Monitoring</li>
        <li>🎯 Intelligent Automation</li>
        </ul>
        
        <b>How can I help you today?</b>
        """
        
        self.chat_display.setHtml(welcome)
        
    @Slot()
    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return
            
        # Check if already processing
        if self.worker_thread and self.worker_thread.isRunning():
            self.add_message("System", "Please wait for the current command to complete.", is_user=False)
            return
            
        # Add user message to chat
        self.add_message("You", message, is_user=True)
        
        # Clear input and disable controls
        self.input_field.clear()
        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # Emit signal
        self.command_sent.emit(message)
        
        # Process command in worker thread
        self.worker_thread = AIWorkerThread(message, self.api_url)
        self.worker_thread.response_ready.connect(self.on_response_ready)
        self.worker_thread.error_occurred.connect(self.on_error_occurred)
        self.worker_thread.finished.connect(self.on_processing_finished)
        self.worker_thread.start()
        
    def add_message(self, sender, message, is_user=False):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Add some spacing
        cursor.insertText("\n\n")
        
        # Format based on sender with better styling
        if is_user:
            cursor.insertHtml(f"<div style='margin: 10px 0;'><b style='color: #2196F3;'>{sender}:</b> <span style='color: #333;'>{message}</span></div>")
        else:
            cursor.insertHtml(f"<div style='margin: 10px 0; background-color: #f5f5f5; padding: 10px; border-radius: 5px;'><b style='color: #4CAF50;'>{sender}:</b> <span style='color: #333;'>{message}</span></div>")
            
        # Scroll to bottom
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
        
    @Slot(str)
    def on_response_ready(self, response):
        """Handle successful AI response"""
        self.add_message("AI Assistant", response, is_user=False)
        self.response_received.emit(response)
        
    @Slot(str)
    def on_error_occurred(self, error):
        """Handle AI processing error"""
        error_msg = f"""<span style='color: #f44336;'>⚠️ Error:</span> {error}
        <br><br>
        <i>The AI assistant encountered an issue. Please try:
        <ul>
        <li>Checking your network connection</li>
        <li>Ensuring the backend service is running</li>
        <li>Rephrasing your command</li>
        </ul></i>"""
        self.add_message("AI Assistant", error_msg, is_user=False)
        
    @Slot()
    def on_processing_finished(self):
        """Re-enable controls after processing is complete"""
        self.progress_bar.setVisible(False)
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        
    @Slot()
    def use_suggestion(self, item):
        suggestion = item.text()
        self.input_field.setText(suggestion)
        self.send_message()
        
    def refresh(self):
        # Could refresh AI model or context
        pass