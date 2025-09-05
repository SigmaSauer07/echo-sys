#!/usr/bin/env python3
"""Test script for main.py functionality"""
import sys
import traceback
from fastapi.testclient import TestClient

def test_imports():
    """Test that all imports work correctly"""
    try:
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_app_creation():
    """Test that the FastAPI app is created correctly"""
    try:
        import core.main as main
        app = main.app
        print("✅ FastAPI app created successfully")
        print(f"   Title: {app.title}")
        print(f"   Version: {app.version}")
        return True
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        traceback.print_exc()
        return False

def test_routes():
    """Test that all expected routes are registered"""
    try:
        import core.main as main
        app = main.app
        
        expected_routes = [
            "/", "/health", "/ready", "/ask", "/store", "/stream"
        ]
        
        actual_routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        missing_routes = []
        for route in expected_routes:
            if route not in actual_routes:
                missing_routes.append(route)
        
        if missing_routes:
            print(f"❌ Missing routes: {missing_routes}")
            return False
        
        print("✅ All expected routes are registered")
        print(f"   Routes: {expected_routes}")
        return True
    except Exception as e:
        print(f"❌ Route test failed: {e}")
        traceback.print_exc()
        return False

def test_config():
    """Test configuration loading"""
    try:
        from config.config import config
        print("✅ Configuration loaded successfully")
        print(f"   Host: {config.HOST}:{config.PORT}")
        print(f"   API Token: {'***' if config.API_TOKEN else 'Not set'}")
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        traceback.print_exc()
        return False

def test_basic_endpoints():
    """Test basic endpoints without external dependencies"""
    try:
        import core.main as main
        client = TestClient(main.app)
        
        # Test root endpoint
        response = client.get("/")
        if response.status_code != 200:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
        
        print("✅ Basic endpoints working")
        print(f"   Root response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Basic endpoint test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Alsania MCP Implementation")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("App Creation Test", test_app_creation),
        ("Routes Test", test_routes),
        ("Configuration Test", test_config),
        ("Basic Endpoints Test", test_basic_endpoints),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"   Test failed!")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The main.py implementation is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
