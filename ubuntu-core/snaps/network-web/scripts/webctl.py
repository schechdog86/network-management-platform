#!/usr/bin/env python3
"""
Network Web Interface Control CLI
"""

import click
import requests
import subprocess
import os
import json

WEB_URL = f"http://localhost:{os.environ.get('PORT', '3000')}"
API_URL = os.environ.get('REACT_APP_API_URL', 'http://localhost:8000')

@click.group()
def cli():
    """Network Web Interface Control"""
    pass

@cli.command()
def status():
    """Check web interface status"""
    try:
        # Check web server
        response = requests.get(WEB_URL, timeout=5)
        if response.status_code == 200:
            click.echo(f"✓ Web interface is running at {WEB_URL}")
        else:
            click.echo(f"✗ Web interface returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        click.echo(f"✗ Web interface is not responding at {WEB_URL}")
    except Exception as e:
        click.echo(f"✗ Error checking web interface: {e}")
    
    # Check API connection
    try:
        response = requests.get(f"{API_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            click.echo(f"✓ API backend is available at {API_URL}")
        else:
            click.echo(f"✗ API backend returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        click.echo(f"✗ API backend is not responding at {API_URL}")
    except Exception as e:
        click.echo(f"✗ Error checking API: {e}")

@cli.command()
def logs():
    """Show web server logs"""
    log_file = f"{os.environ['SNAP_DATA']}/logs/web-server.log"
    if os.path.exists(log_file):
        subprocess.run(['tail', '-f', log_file])
    else:
        click.echo("No log file found")

@cli.command()
def config():
    """Show current configuration"""
    config_data = {
        "web_url": WEB_URL,
        "api_url": API_URL,
        "port": os.environ.get('PORT', '3000'),
        "node_env": os.environ.get('NODE_ENV', 'production'),
        "snap_data": os.environ.get('SNAP_DATA', 'N/A')
    }
    
    click.echo(json.dumps(config_data, indent=2))

@cli.command()
@click.option('--port', default=3000, help='Port to check')
def healthcheck(port):
    """Perform health check"""
    checks = {
        "web_server": False,
        "api_connection": False,
        "static_assets": False
    }
    
    # Check web server
    try:
        response = requests.get(f"http://localhost:{port}", timeout=5)
        checks["web_server"] = response.status_code == 200
    except:
        pass
    
    # Check API connection
    try:
        response = requests.get(f"{API_URL}/api/v1/health", timeout=5)
        checks["api_connection"] = response.status_code == 200
    except:
        pass
    
    # Check static assets
    try:
        response = requests.get(f"http://localhost:{port}/static/js/main.js", timeout=5)
        checks["static_assets"] = response.status_code == 200
    except:
        pass
    
    # Print results
    all_passed = all(checks.values())
    
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        click.echo(f"{status} {check}")
    
    if all_passed:
        click.echo("\nAll health checks passed!")
        return 0
    else:
        click.echo("\nSome health checks failed!")
        return 1

@cli.command()
def restart():
    """Restart the web server"""
    click.echo("Restarting web server...")
    subprocess.run(['snapctl', 'restart', 'network-web.web-server'])
    click.echo("Web server restarted")

@cli.command()
def cache_clear():
    """Clear web cache"""
    cache_dir = f"{os.environ['SNAP_DATA']}/cache"
    if os.path.exists(cache_dir):
        subprocess.run(['rm', '-rf', f"{cache_dir}/*"])
        click.echo("Cache cleared")
    else:
        click.echo("No cache directory found")

if __name__ == '__main__':
    cli()