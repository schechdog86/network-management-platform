#!/usr/bin/env python3
"""Test script to verify all imports are working correctly"""

import sys
import traceback

def test_import(module_name):
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
        return True
    except Exception as e:
        print(f"✗ {module_name}: {e}")
        traceback.print_exc()
        return False

# Test core modules
modules = [
    "app.core.config",
    "app.core.database",
    "app.core.redis_client",
    "app.core.security",
    
    # Models
    "app.models.device",
    "app.models.user",
    "app.models.network",
    "app.models.backup",
    "app.models.pxe",
    
    # Services
    "app.services.ssh_manager",
    "app.services.snmp_manager",
    "app.services.network_discovery",
    "app.services.backup_service",
    "app.services.pxe_server",
    "app.services.websocket_manager",
    "app.services.wake_on_lan",
    "app.services.system_metrics",
    
    # API routes
    "app.api.v1.auth",
    "app.api.v1.devices",
    "app.api.v1.network",
    "app.api.v1.ssh",
    "app.api.v1.backup",
    "app.api.v1.pxe",
    "app.api.v1.snmp",
    "app.api.v1.wake_on_lan",
    "app.api.v1.metrics",
    
    # Main app
    "app.main",
]

print("Testing imports...")
print("=" * 50)

failed = []
for module in modules:
    if not test_import(module):
        failed.append(module)

print("=" * 50)
if failed:
    print(f"\n{len(failed)} modules failed to import:")
    for m in failed:
        print(f"  - {m}")
    sys.exit(1)
else:
    print(f"\nAll {len(modules)} modules imported successfully!")
    sys.exit(0)