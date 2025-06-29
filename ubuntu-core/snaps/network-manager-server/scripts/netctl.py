#!/usr/bin/env python3
"""
Network Manager Server Control CLI
"""

import click
import requests
import json
import sys
from typing import Optional

API_BASE = "http://localhost:8000/api/v1"

@click.group()
def cli():
    """Network Manager Server Control"""
    pass

@cli.command()
def status():
    """Check server status"""
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            data = response.json()
            click.echo(f"Server Status: {data.get('status', 'unknown')}")
            click.echo(f"Version: {data.get('version', 'unknown')}")
            click.echo(f"Uptime: {data.get('uptime', 'unknown')}")
        else:
            click.echo(f"Error: Server returned {response.status_code}")
    except requests.exceptions.ConnectionError:
        click.echo("Error: Cannot connect to server")
        sys.exit(1)

@cli.group()
def device():
    """Device management commands"""
    pass

@device.command()
def list():
    """List all devices"""
    try:
        response = requests.get(f"{API_BASE}/devices")
        if response.status_code == 200:
            devices = response.json()
            if devices:
                click.echo(f"{'ID':<10} {'Name':<20} {'IP':<15} {'Status':<10}")
                click.echo("-" * 60)
                for dev in devices:
                    click.echo(f"{dev['id']:<10} {dev['name']:<20} {dev['ip_address']:<15} {dev['status']:<10}")
            else:
                click.echo("No devices found")
        else:
            click.echo(f"Error: {response.status_code}")
    except Exception as e:
        click.echo(f"Error: {e}")

@device.command()
@click.argument('device_id')
def wake(device_id):
    """Wake a device using Wake-on-LAN"""
    try:
        response = requests.post(f"{API_BASE}/wake_on_lan/{device_id}/wake")
        if response.status_code == 200:
            click.echo(f"Wake-on-LAN packet sent to device {device_id}")
        else:
            click.echo(f"Error: {response.status_code}")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.group()
def backup():
    """Backup management commands"""
    pass

@backup.command()
@click.argument('device_id')
def create(device_id):
    """Create a backup for a device"""
    try:
        response = requests.post(f"{API_BASE}/backup/{device_id}/backup")
        if response.status_code == 200:
            result = response.json()
            click.echo(f"Backup initiated: {result.get('task_id')}")
        else:
            click.echo(f"Error: {response.status_code}")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.group()
def metrics():
    """Metrics and monitoring commands"""
    pass

@metrics.command()
@click.argument('device_id')
def show(device_id):
    """Show metrics for a device"""
    try:
        response = requests.get(f"{API_BASE}/metrics/{device_id}/current")
        if response.status_code == 200:
            data = response.json()
            click.echo(f"Device {device_id} Metrics:")
            click.echo(f"  CPU Usage: {data.get('cpu_usage', 'N/A')}%")
            click.echo(f"  Memory Usage: {data.get('memory_usage', 'N/A')}%")
            click.echo(f"  Disk Usage: {data.get('disk_usage', 'N/A')}%")
            if 'gpu_usage' in data:
                click.echo(f"  GPU Usage: {data['gpu_usage']}%")
        else:
            click.echo(f"Error: {response.status_code}")
    except Exception as e:
        click.echo(f"Error: {e}")

if __name__ == '__main__':
    cli()