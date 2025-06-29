#!/usr/bin/env python3
"""
Main entry point for the Network Management Desktop Application
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from desktop.ui.main_window import MainWindow
from desktop.utils.config import load_config

def main():
    # Enable high DPI scaling
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Network Manager")
    app.setOrganizationName("NetworkManagement")
    
    # Load configuration
    config = load_config()
    
    # Create and show main window
    window = MainWindow(config)
    window.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()