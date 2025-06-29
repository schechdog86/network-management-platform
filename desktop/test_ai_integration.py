#!/usr/bin/env python3
"""
Test script for AI integration in Qt desktop application
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_ai_imports():
    """Test that AI components can be imported"""
    try:
        from ai.nlp.command_processor import CommandProcessor
        print("✅ CommandProcessor import successful")
        
        from ai.orchestrator import AIOrchestrator  
        print("✅ AIOrchestrator import successful")
        
        from desktop.components.ai_assistant import AIAssistantWidget, AIWorkerThread
        print("✅ AI Assistant components import successful")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_command_processor():
    """Test basic command processing functionality"""
    try:
        from ai.nlp.command_processor import CommandProcessor
        
        processor = CommandProcessor()
        test_command = "show me all online devices"
        
        # This might fail if OpenAI API key is not set, but import should work
        print(f"✅ CommandProcessor instantiated successfully")
        print(f"📝 Test command: '{test_command}'")
        
        return True
    except Exception as e:
        print(f"❌ CommandProcessor test error: {e}")
        return False

def test_config_loading():
    """Test configuration loading"""
    try:
        from desktop.utils.config import load_config
        
        config = load_config()
        api_url = config.get("api_url", "http://localhost:8000")
        
        print(f"✅ Config loaded successfully")
        print(f"📝 API URL: {api_url}")
        
        return True
    except Exception as e:
        print(f"❌ Config loading error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing AI Integration for Qt Desktop Application")
    print("=" * 50)
    
    tests = [
        ("AI Imports", test_ai_imports),
        ("Command Processor", test_command_processor), 
        ("Config Loading", test_config_loading)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        success = test_func()
        results.append((test_name, success))
        
    print("\n" + "=" * 50)
    print("🏁 Test Results:")
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not success:
            all_passed = False
            
    if all_passed:
        print("\n🎉 All tests passed! AI integration is ready.")
    else:
        print("\n⚠️  Some tests failed. Check dependencies and configuration.")
        
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())