"""
Theme Manager for Dark/Light mode support
"""

from PySide6.QtCore import QObject, Signal, QSettings
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QStyleFactory
from typing import Dict, Any

class ThemeManager(QObject):
    """Manages application themes (dark/light mode)"""
    
    theme_changed = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("NetworkManager", "Desktop")
        self.current_theme = self.settings.value("theme", "light")
        self.themes = {
            "light": self._get_light_theme(),
            "dark": self._get_dark_theme(),
            "system": self._get_system_theme()
        }
        
    def _get_light_theme(self) -> Dict[str, Any]:
        """Light theme configuration"""
        return {
            "name": "light",
            "style": "Fusion",
            "palette": {
                "Window": QColor(240, 240, 240),
                "WindowText": QColor(0, 0, 0),
                "Base": QColor(255, 255, 255),
                "AlternateBase": QColor(233, 233, 233),
                "ToolTipBase": QColor(255, 255, 220),
                "ToolTipText": QColor(0, 0, 0),
                "Text": QColor(0, 0, 0),
                "Button": QColor(240, 240, 240),
                "ButtonText": QColor(0, 0, 0),
                "BrightText": QColor(255, 0, 0),
                "Link": QColor(0, 0, 255),
                "Highlight": QColor(76, 163, 224),
                "HighlightedText": QColor(255, 255, 255),
                "Light": QColor(255, 255, 255),
                "Midlight": QColor(227, 227, 227),
                "Dark": QColor(160, 160, 160),
                "Mid": QColor(180, 180, 180),
                "Shadow": QColor(105, 105, 105)
            },
            "stylesheet": """
                QMainWindow {
                    background-color: #f0f0f0;
                }
                QTabWidget::pane {
                    border: 1px solid #cccccc;
                    background-color: white;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: white;
                    border-bottom: 2px solid #4ca3e0;
                }
                QPushButton {
                    background-color: #4ca3e0;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #3c93d0;
                }
                QPushButton:pressed {
                    background-color: #2c83c0;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QTreeWidget {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
                QLineEdit {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 6px;
                }
                QTextEdit {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
                QProgressBar {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4ca3e0;
                    border-radius: 4px;
                }
            """
        }
        
    def _get_dark_theme(self) -> Dict[str, Any]:
        """Dark theme configuration"""
        return {
            "name": "dark",
            "style": "Fusion",
            "palette": {
                "Window": QColor(53, 53, 53),
                "WindowText": QColor(255, 255, 255),
                "Base": QColor(42, 42, 42),
                "AlternateBase": QColor(66, 66, 66),
                "ToolTipBase": QColor(255, 255, 220),
                "ToolTipText": QColor(0, 0, 0),
                "Text": QColor(255, 255, 255),
                "Button": QColor(53, 53, 53),
                "ButtonText": QColor(255, 255, 255),
                "BrightText": QColor(255, 0, 0),
                "Link": QColor(42, 130, 218),
                "Highlight": QColor(42, 130, 218),
                "HighlightedText": QColor(255, 255, 255),
                "Light": QColor(97, 97, 97),
                "Midlight": QColor(75, 75, 75),
                "Dark": QColor(35, 35, 35),
                "Mid": QColor(60, 60, 60),
                "Shadow": QColor(20, 20, 20)
            },
            "stylesheet": """
                QMainWindow {
                    background-color: #353535;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    background-color: #2a2a2a;
                }
                QTabBar::tab {
                    background-color: #3a3a3a;
                    color: #ffffff;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #2a2a2a;
                    border-bottom: 2px solid #2a82da;
                }
                QPushButton {
                    background-color: #2a82da;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #1a72ca;
                }
                QPushButton:pressed {
                    background-color: #0a62ba;
                }
                QPushButton:disabled {
                    background-color: #555555;
                    color: #888888;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    margin-top: 10px;
                    padding-top: 10px;
                    color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QTreeWidget {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QTreeWidget::item:selected {
                    background-color: #2a82da;
                }
                QTreeWidget::item:hover {
                    background-color: #3a3a3a;
                }
                QLineEdit {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QTextEdit {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QProgressBar {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    text-align: center;
                    color: #ffffff;
                    background-color: #2a2a2a;
                }
                QProgressBar::chunk {
                    background-color: #2a82da;
                    border-radius: 4px;
                }
                QListWidget {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    background-color: #2a82da;
                }
                QListWidget::item:hover {
                    background-color: #3a3a3a;
                }
                QComboBox {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #ffffff;
                    margin-right: 5px;
                }
                QMenuBar {
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #3a3a3a;
                }
                QMenu {
                    background-color: #2a2a2a;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QMenu::item:selected {
                    background-color: #2a82da;
                }
                QStatusBar {
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QToolBar {
                    background-color: #2a2a2a;
                    border: none;
                    spacing: 3px;
                }
                QToolBar::separator {
                    background-color: #555555;
                    width: 1px;
                    margin: 4px;
                }
                QLabel {
                    color: #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QRadioButton {
                    color: #ffffff;
                }
                QSplitter::handle {
                    background-color: #555555;
                }
            """
        }
        
    def _get_system_theme(self) -> Dict[str, Any]:
        """Get system theme (follows OS theme)"""
        # This is a placeholder - would need OS-specific detection
        # For now, default to light theme
        return self._get_light_theme()
        
    def apply_theme(self, theme_name: str = None):
        """Apply the specified theme or current theme"""
        if theme_name:
            self.current_theme = theme_name
            self.settings.setValue("theme", theme_name)
            
        theme = self.themes.get(self.current_theme, self.themes["light"])
        
        # Apply style
        app = QApplication.instance()
        if app:
            app.setStyle(QStyleFactory.create(theme["style"]))
            
            # Create and apply palette
            palette = QPalette()
            for role_name, color in theme["palette"].items():
                role = getattr(QPalette, role_name, None)
                if role is not None:
                    palette.setColor(role, color)
                    
            app.setPalette(palette)
            
            # Apply stylesheet
            app.setStyleSheet(theme["stylesheet"])
            
        self.theme_changed.emit(self.current_theme)
        
    def get_current_theme(self) -> str:
        """Get current theme name"""
        return self.current_theme
        
    def get_available_themes(self) -> list:
        """Get list of available themes"""
        return list(self.themes.keys())
        
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        if self.current_theme == "light":
            self.apply_theme("dark")
        else:
            self.apply_theme("light")
            
    def is_dark_theme(self) -> bool:
        """Check if current theme is dark"""
        return self.current_theme == "dark"

# Global theme manager instance
theme_manager = None

def get_theme_manager() -> ThemeManager:
    """Get or create theme manager instance"""
    global theme_manager
    if not theme_manager:
        theme_manager = ThemeManager()
    return theme_manager