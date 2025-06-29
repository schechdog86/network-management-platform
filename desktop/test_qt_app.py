#!/usr/bin/env python3
"""
Test script for Qt desktop application
"""

import sys
import subprocess

def test_imports():
    """Test that all required imports work"""
    try:
        print("Testing PySide6 imports...")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        print("✓ PySide6 imports successful")
        
        print("\nTesting application imports...")
        from desktop.ui.main_window import MainWindow
        from desktop.utils.config import load_config
        from desktop.utils.api_client import get_api_client
        from desktop.utils.theme_manager import get_theme_manager
        print("✓ Application imports successful")
        
        print("\nTesting component imports...")
        from desktop.components.network_overview import NetworkOverviewWidget
        from desktop.components.monitoring import MonitoringWidget
        from desktop.components.ai_assistant import AIAssistantWidget
        print("✓ Component imports successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_config():
    """Test configuration loading"""
    try:
        print("\nTesting configuration...")
        from desktop.utils.config import load_config
        config = load_config()
        print(f"✓ Config loaded successfully")
        print(f"  API URL: {config.get('api.base_url')}")
        print(f"  Theme: {config.get('ui.theme')}")
        return True
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False

def test_theme_manager():
    """Test theme manager"""
    try:
        print("\nTesting theme manager...")
        from desktop.utils.theme_manager import ThemeManager
        theme_mgr = ThemeManager()
        themes = theme_mgr.get_available_themes()
        print(f"✓ Theme manager initialized")
        print(f"  Available themes: {themes}")
        print(f"  Current theme: {theme_mgr.get_current_theme()}")
        return True
    except Exception as e:
        print(f"✗ Theme manager test failed: {e}")
        return False

def test_api_client():
    """Test API client"""
    try:
        print("\nTesting API client...")
        from desktop.utils.api_client import APIClient
        client = APIClient("http://localhost:8000")
        print("✓ API client created successfully")
        
        # Test connection (may fail if backend not running)
        print("  Testing backend connection...")
        result = client.get_network_status()
        if result.get("success"):
            print("  ✓ Backend is reachable")
        else:
            print("  ⚠ Backend not reachable (this is OK for testing)")
        
        return True
    except Exception as e:
        print(f"✗ API client test failed: {e}")
        return False

def main():
    print("Qt Desktop Application Test Suite")
    print("=================================\n")
    
    # Run tests
    tests = [
        test_imports,
        test_config,
        test_theme_manager,
        test_api_client
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n\nSummary: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("\n✓ All tests passed! The application should be ready to run.")
        print("\nTo run the application:")
        print("  cd /home/edward/network")
        print("  python desktop/main.py")
    else:
        print("\n✗ Some tests failed. Please check the dependencies.")
        print("\nTo install dependencies:")
        print("  cd /home/edward/network/desktop")
        print("  pip install -r requirements.txt")

if __name__ == "__main__":
    main()