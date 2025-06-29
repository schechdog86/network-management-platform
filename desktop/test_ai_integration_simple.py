#!/usr/bin/env python3
"""
Simple test script for AI integration in Qt desktop application
Tests imports and basic functionality without requiring API keys
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_basic_imports():
    """Test that basic components can be imported"""
    try:
        # Test Qt components first
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread
        print("✅ PySide6 imports successful")
        
        # Test config loading
        from desktop.utils.config import load_config
        print("✅ Config utilities import successful")
        
        # Test AI assistant widget (should not trigger LLM initialization)
        from desktop.components.ai_assistant import AIAssistantWidget, AIWorkerThread
        print("✅ AI Assistant widget components import successful")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config_functionality():
    """Test configuration loading and basic functionality"""
    try:
        from desktop.utils.config import load_config
        
        config = load_config()
        api_url = config.get("api_url", "http://localhost:8000")
        ai_enabled = config.get("ai.enabled", True)
        
        print(f"✅ Config loaded successfully")
        print(f"📝 API URL: {api_url}")
        print(f"📝 AI Enabled: {ai_enabled}")
        
        return True
    except Exception as e:
        print(f"❌ Config test error: {e}")
        return False

def test_worker_thread_creation():
    """Test that worker thread can be created"""
    try:
        from desktop.components.ai_assistant import AIWorkerThread
        
        # Create worker thread (but don't start it)
        worker = AIWorkerThread("test command", "http://localhost:8000")
        
        print(f"✅ AI Worker thread created successfully")
        print(f"📝 Command: {worker.command}")
        print(f"📝 API URL: {worker.api_url}")
        
        return True
    except Exception as e:
        print(f"❌ Worker thread test error: {e}")
        return False

def test_requests_functionality():
    """Test that requests library works for API calls"""
    try:
        import requests
        
        # Test a simple request (won't actually connect)
        try:
            # This will fail but shouldn't crash
            response = requests.get("http://localhost:8000/health", timeout=1)
        except (requests.ConnectionError, requests.Timeout):
            # Expected when backend is not running
            pass
            
        print("✅ Requests library working")
        return True
    except Exception as e:
        print(f"❌ Requests test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing AI Integration for Qt Desktop Application (Simple)")
    print("=" * 60)
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Config Functionality", test_config_functionality),
        ("Worker Thread Creation", test_worker_thread_creation),
        ("Requests Functionality", test_requests_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        success = test_func()
        results.append((test_name, success))
        
    print("\n" + "=" * 60)
    print("🏁 Test Results:")
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not success:
            all_passed = False
            
    if all_passed:
        print("\n🎉 All basic tests passed! AI integration components are ready.")
        print("\n📝 Note: Full AI functionality requires:")
        print("  - Backend service running on configured API URL")
        print("  - OpenAI API key (for LLM functionality)")
        print("  - Anthropic API key (for advanced features)")
    else:
        print("\n⚠️  Some tests failed. Check dependencies and configuration.")
        
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())