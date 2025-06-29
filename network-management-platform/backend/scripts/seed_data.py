#!/usr/bin/env python3
"""
Seed the database with initial data for development/testing
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random
import json

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.device import Device
from app.models.network import NetworkScan
from app.models.system import DeviceMetric

async def create_users(db: AsyncSession):
    """Create sample users"""
    print("Creating users...")
    
    users_data = [
        {
            "username": "admin",
            "email": "admin@example.com",
            "full_name": "Admin User",
            "password": "admin123",
            "is_admin": True,
            "is_active": True
        },
        {
            "username": "operator",
            "email": "operator@example.com",
            "full_name": "Network Operator",
            "password": "operator123",
            "is_admin": False,
            "is_active": True
        },
        {
            "username": "viewer",
            "email": "viewer@example.com",
            "full_name": "Read Only User",
            "password": "viewer123",
            "is_admin": False,
            "is_active": True
        }
    ]
    
    for user_data in users_data:
        # Check if user already exists
        existing = await db.execute(
            f"SELECT id FROM users WHERE username = '{user_data['username']}'"
        )
        if existing.fetchone():
            print(f"  User {user_data['username']} already exists, skipping...")
            continue
            
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            hashed_password=get_password_hash(user_data["password"]),
            is_admin=user_data["is_admin"],
            is_active=user_data["is_active"]
        )
        db.add(user)
        print(f"  Created user: {user.username}")
    
    await db.commit()
    print("✅ Users created successfully!")

async def create_devices(db: AsyncSession):
    """Create sample devices"""
    print("\nCreating devices...")
    
    device_types = ["router", "switch", "server", "workstation", "firewall", "access_point"]
    vendors = ["Cisco", "Juniper", "Dell", "HP", "Ubiquiti", "MikroTik"]
    
    devices_data = []
    
    # Create routers
    for i in range(1, 4):
        devices_data.append({
            "ip_address": f"192.168.1.{i}",
            "hostname": f"router-{i:02d}",
            "mac_address": f"00:11:22:33:44:{i:02X}",
            "device_type": "router",
            "vendor": random.choice(["Cisco", "Juniper"]),
            "status": "online",
            "snmp_enabled": True,
            "snmp_community": "public",
            "ssh_enabled": True,
            "ssh_username": "admin"
        })
    
    # Create switches
    for i in range(1, 6):
        devices_data.append({
            "ip_address": f"192.168.1.{10 + i}",
            "hostname": f"switch-{i:02d}",
            "mac_address": f"00:AA:BB:CC:DD:{i:02X}",
            "device_type": "switch",
            "vendor": random.choice(["Cisco", "HP"]),
            "status": "online" if i < 4 else "offline",
            "snmp_enabled": True,
            "snmp_community": "public"
        })
    
    # Create servers
    for i in range(1, 11):
        devices_data.append({
            "ip_address": f"192.168.1.{100 + i}",
            "hostname": f"server-{i:02d}",
            "mac_address": f"00:DE:AD:BE:EF:{i:02X}",
            "device_type": "server",
            "vendor": random.choice(["Dell", "HP"]),
            "status": "online" if i < 8 else "offline",
            "ssh_enabled": True,
            "ssh_username": "root"
        })
    
    # Create workstations
    for i in range(1, 21):
        devices_data.append({
            "ip_address": f"192.168.1.{150 + i}",
            "hostname": f"workstation-{i:02d}",
            "mac_address": f"00:CA:FE:BA:BE:{i:02X}",
            "device_type": "workstation",
            "vendor": random.choice(["Dell", "HP", "Lenovo"]),
            "status": random.choice(["online", "offline", "unknown"])
        })
    
    for device_data in devices_data:
        # Check if device already exists
        existing = await db.execute(
            f"SELECT id FROM devices WHERE ip_address = '{device_data['ip_address']}'"
        )
        if existing.fetchone():
            print(f"  Device {device_data['ip_address']} already exists, skipping...")
            continue
            
        device = Device(**device_data)
        device.last_seen = datetime.utcnow() if device.status == "online" else None
        db.add(device)
        print(f"  Created device: {device.hostname} ({device.ip_address})")
    
    await db.commit()
    print("✅ Devices created successfully!")

async def create_device_metrics(db: AsyncSession):
    """Create sample device metrics"""
    print("\nCreating device metrics...")
    
    # Get all online devices
    result = await db.execute("SELECT id, device_type FROM devices WHERE status = 'online'")
    devices = result.fetchall()
    
    if not devices:
        print("  No online devices found, skipping metrics...")
        return
    
    metric_types = {
        "router": ["cpu_usage", "memory_usage", "bandwidth_in", "bandwidth_out", "packet_loss"],
        "switch": ["cpu_usage", "memory_usage", "port_utilization", "error_rate"],
        "server": ["cpu_usage", "memory_usage", "disk_usage", "network_io", "load_average"],
        "workstation": ["cpu_usage", "memory_usage", "disk_usage"],
        "firewall": ["cpu_usage", "memory_usage", "connections", "blocked_packets"],
        "access_point": ["cpu_usage", "memory_usage", "client_count", "signal_strength"]
    }
    
    # Create metrics for the last 24 hours
    now = datetime.utcnow()
    metrics_count = 0
    
    for device_id, device_type in devices:
        metrics = metric_types.get(device_type, ["cpu_usage", "memory_usage"])
        
        # Generate hourly metrics for the last 24 hours
        for hours_ago in range(24, -1, -1):
            timestamp = now - timedelta(hours=hours_ago)
            
            for metric_type in metrics:
                # Generate realistic values based on metric type
                if metric_type == "cpu_usage":
                    value = random.uniform(10, 90)
                    unit = "percent"
                elif metric_type == "memory_usage":
                    value = random.uniform(20, 80)
                    unit = "percent"
                elif metric_type == "disk_usage":
                    value = random.uniform(30, 70)
                    unit = "percent"
                elif metric_type in ["bandwidth_in", "bandwidth_out", "network_io"]:
                    value = random.uniform(100, 10000)
                    unit = "Mbps"
                elif metric_type == "packet_loss":
                    value = random.uniform(0, 5)
                    unit = "percent"
                elif metric_type == "port_utilization":
                    value = random.uniform(10, 100)
                    unit = "percent"
                elif metric_type == "error_rate":
                    value = random.uniform(0, 2)
                    unit = "percent"
                elif metric_type == "load_average":
                    value = random.uniform(0.5, 4.0)
                    unit = "load"
                elif metric_type == "connections":
                    value = random.randint(100, 5000)
                    unit = "count"
                elif metric_type == "blocked_packets":
                    value = random.randint(0, 1000)
                    unit = "count"
                elif metric_type == "client_count":
                    value = random.randint(5, 50)
                    unit = "count"
                elif metric_type == "signal_strength":
                    value = random.uniform(-80, -30)
                    unit = "dBm"
                else:
                    value = random.uniform(0, 100)
                    unit = "units"
                
                metric = DeviceMetric(
                    timestamp=timestamp,
                    device_id=device_id,
                    metric_type=metric_type,
                    value=value,
                    unit=unit
                )
                db.add(metric)
                metrics_count += 1
    
    await db.commit()
    print(f"✅ Created {metrics_count} device metrics!")

async def create_network_scans(db: AsyncSession):
    """Create sample network scan history"""
    print("\nCreating network scan history...")
    
    scans_data = [
        {
            "id": "scan-001",
            "subnets": ["192.168.1.0/24"],
            "scan_type": "ping",
            "status": "completed",
            "progress": 100,
            "discovered_devices": 38,
            "started_at": datetime.utcnow() - timedelta(days=7),
            "completed_at": datetime.utcnow() - timedelta(days=7, hours=-1),
            "results": {"discovered": 38, "online": 25, "offline": 13}
        },
        {
            "id": "scan-002",
            "subnets": ["192.168.1.0/24", "192.168.2.0/24"],
            "scan_type": "detailed",
            "status": "completed",
            "progress": 100,
            "discovered_devices": 52,
            "started_at": datetime.utcnow() - timedelta(days=3),
            "completed_at": datetime.utcnow() - timedelta(days=3, hours=-2),
            "results": {"discovered": 52, "online": 35, "offline": 17}
        },
        {
            "id": "scan-003",
            "subnets": ["192.168.1.0/24"],
            "scan_type": "ping",
            "status": "in_progress",
            "progress": 65,
            "discovered_devices": 24,
            "started_at": datetime.utcnow() - timedelta(minutes=10),
            "completed_at": None,
            "results": None
        }
    ]
    
    for scan_data in scans_data:
        # Check if scan already exists
        existing = await db.execute(
            f"SELECT id FROM network_scans WHERE id = '{scan_data['id']}'"
        )
        if existing.fetchone():
            print(f"  Scan {scan_data['id']} already exists, skipping...")
            continue
            
        scan = NetworkScan(**scan_data)
        db.add(scan)
        print(f"  Created scan: {scan.id}")
    
    await db.commit()
    print("✅ Network scans created successfully!")

async def main():
    """Main function to seed all data"""
    print("🌱 Seeding database with sample data...")
    print("=" * 60)
    
    # Initialize database
    await init_db()
    
    # Create session
    async with AsyncSessionLocal() as db:
        try:
            # Seed data in order
            await create_users(db)
            await create_devices(db)
            await create_device_metrics(db)
            await create_network_scans(db)
            
            print("\n✅ Database seeding completed successfully!")
            print("\nDefault users created:")
            print("  - admin / admin123 (Administrator)")
            print("  - operator / operator123 (Network Operator)")
            print("  - viewer / viewer123 (Read-only User)")
            
        except Exception as e:
            print(f"\n❌ Error seeding database: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(main())