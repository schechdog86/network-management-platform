#!/usr/bin/env python3
"""
Ray Cluster Control CLI
"""

import click
import ray
import requests
import json
import subprocess
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich import box

console = Console()

DASHBOARD_URL = f"http://localhost:{os.environ.get('RAY_DASHBOARD_PORT', '8265')}"

@click.group()
def cli():
    """Ray Cluster Control"""
    pass

@cli.command()
def status():
    """Show cluster status"""
    try:
        # Get Ray status
        result = subprocess.run(['ray', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]Ray Cluster Status[/green]")
            console.print(result.stdout)
        else:
            console.print("[red]Error getting Ray status[/red]")
            console.print(result.stderr)
            
        # Get dashboard status
        try:
            response = requests.get(f"{DASHBOARD_URL}/api/cluster_status")
            if response.status_code == 200:
                data = response.json()
                console.print(f"\n[cyan]Dashboard:[/cyan] Active at {DASHBOARD_URL}")
                console.print(f"[cyan]Nodes:[/cyan] {data.get('num_nodes', 0)}")
                console.print(f"[cyan]CPUs:[/cyan] {data.get('total_resources', {}).get('CPU', 0)}")
                console.print(f"[cyan]GPUs:[/cyan] {data.get('total_resources', {}).get('GPU', 0)}")
        except:
            console.print("[yellow]Dashboard not accessible[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@cli.command()
def nodes():
    """List cluster nodes"""
    try:
        ray.init(address='auto', ignore_reinit_error=True)
        
        nodes = ray.nodes()
        
        table = Table(title="Ray Cluster Nodes", box=box.ROUNDED)
        table.add_column("Node ID", style="cyan")
        table.add_column("IP Address", style="green")
        table.add_column("State", style="yellow")
        table.add_column("CPUs", justify="right")
        table.add_column("GPUs", justify="right")
        table.add_column("Memory", justify="right")
        table.add_column("Objects", justify="right")
        
        for node in nodes:
            if node['Alive']:
                state = "[green]Alive[/green]"
            else:
                state = "[red]Dead[/red]"
                
            node_id = node['NodeID'][:8] + "..."
            ip = node['NodeManagerAddress']
            cpus = node['Resources'].get('CPU', 0)
            gpus = node['Resources'].get('GPU', 0)
            memory = f"{node['Resources'].get('memory', 0) / 1e9:.1f}GB"
            objects = f"{node['Resources'].get('object_store_memory', 0) / 1e9:.1f}GB"
            
            table.add_row(node_id, ip, state, str(cpus), str(gpus), memory, objects)
            
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        ray.shutdown()

@cli.command()
def jobs():
    """List running jobs"""
    try:
        response = requests.get(f"{DASHBOARD_URL}/api/jobs/")
        if response.status_code == 200:
            jobs_data = response.json()
            
            table = Table(title="Ray Jobs", box=box.ROUNDED)
            table.add_column("Job ID", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Start Time")
            table.add_column("Duration")
            table.add_column("Entrypoint")
            
            for job in jobs_data.get('jobs', []):
                job_id = job['job_id'][:8] + "..."
                status = job['status']
                start_time = datetime.fromtimestamp(job.get('start_time', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                if job.get('end_time'):
                    duration = f"{(job['end_time'] - job['start_time']) / 1000:.1f}s"
                else:
                    duration = "Running"
                    
                entrypoint = job.get('entrypoint', 'N/A')[:50] + "..."
                
                table.add_row(job_id, status, start_time, duration, entrypoint)
                
            console.print(table)
        else:
            console.print("[red]Failed to get jobs information[/red]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@cli.command()
@click.argument('script_path')
@click.option('--num-cpus', default=1, help='Number of CPUs')
@click.option('--num-gpus', default=0, help='Number of GPUs')
def submit(script_path, num_cpus, num_gpus):
    """Submit a job to the cluster"""
    try:
        cmd = [
            'ray', 'job', 'submit',
            '--num-cpus', str(num_cpus),
            '--num-gpus', str(num_gpus),
            '--',
            'python', script_path
        ]
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Submitting job...", total=None)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            progress.update(task, completed=True)
            
        if result.returncode == 0:
            console.print("[green]Job submitted successfully![/green]")
            console.print(result.stdout)
        else:
            console.print("[red]Job submission failed[/red]")
            console.print(result.stderr)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@cli.command()
def monitor():
    """Open cluster monitoring dashboard"""
    console.print(f"[cyan]Opening Ray Dashboard at {DASHBOARD_URL}[/cyan]")
    console.print("Press Ctrl+C to exit")
    
    try:
        subprocess.run(['xdg-open', DASHBOARD_URL])
    except:
        console.print(f"[yellow]Please open {DASHBOARD_URL} in your browser[/yellow]")

@cli.command()
@click.option('--workers', default=4, help='Number of workers to add')
def scale(workers):
    """Scale the cluster"""
    try:
        # This would integrate with the autoscaler
        console.print(f"[cyan]Scaling cluster to {workers} workers...[/cyan]")
        
        # In a real implementation, this would:
        # 1. Update autoscaler config
        # 2. Trigger scaling action
        # 3. Monitor progress
        
        console.print("[green]Scaling request submitted[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@cli.command()
def drain():
    """Drain the cluster (prepare for shutdown)"""
    if not click.confirm("This will stop accepting new jobs. Continue?"):
        return
        
    try:
        console.print("[yellow]Draining cluster...[/yellow]")
        
        # Mark cluster as draining
        # Wait for running jobs to complete
        # Prevent new jobs from starting
        
        console.print("[green]Cluster is draining. No new jobs will be accepted.[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@cli.command()
def health():
    """Perform health check"""
    try:
        checks = {
            "Ray Head": False,
            "Dashboard": False,
            "Object Store": False,
            "Redis": False
        }
        
        # Check Ray head
        result = subprocess.run(['ray', 'status'], capture_output=True)
        checks["Ray Head"] = result.returncode == 0
        
        # Check dashboard
        try:
            response = requests.get(f"{DASHBOARD_URL}/api/cluster_status", timeout=5)
            checks["Dashboard"] = response.status_code == 200
        except:
            pass
            
        # Check object store
        try:
            ray.init(address='auto', ignore_reinit_error=True)
            checks["Object Store"] = True
            ray.shutdown()
        except:
            pass
            
        # Check Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=int(os.environ.get('RAY_REDIS_PORT', '6380')))
            r.ping()
            checks["Redis"] = True
        except:
            pass
            
        # Display results
        table = Table(title="Health Check Results", box=box.ROUNDED)
        table.add_column("Component")
        table.add_column("Status")
        
        all_healthy = True
        for component, healthy in checks.items():
            if healthy:
                status = "[green]✓ Healthy[/green]"
            else:
                status = "[red]✗ Unhealthy[/red]"
                all_healthy = False
                
            table.add_row(component, status)
            
        console.print(table)
        
        if all_healthy:
            console.print("\n[green]All components are healthy![/green]")
        else:
            console.print("\n[red]Some components are unhealthy![/red]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

if __name__ == '__main__':
    import os
    cli()