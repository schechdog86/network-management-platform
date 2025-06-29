#!/usr/bin/env python3
"""
Network Database Control CLI
"""

import click
import psycopg2
import os
import subprocess
from datetime import datetime
from tabulate import tabulate

# Database connection parameters
DB_PARAMS = {
    'host': os.environ.get('PGHOST', 'localhost'),
    'port': os.environ.get('PGPORT', '5432'),
    'database': os.environ.get('POSTGRES_DB', 'networkdb'),
    'user': os.environ.get('POSTGRES_USER', 'netmanager'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'password')
}

def get_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_PARAMS)

@click.group()
def cli():
    """Network Database Control"""
    pass

@cli.command()
def status():
    """Check database status"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check PostgreSQL version
        cur.execute("SELECT version()")
        pg_version = cur.fetchone()[0]
        click.echo(f"PostgreSQL: {pg_version.split(',')[0]}")
        
        # Check TimescaleDB version
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        ts_version = cur.fetchone()
        if ts_version:
            click.echo(f"TimescaleDB: v{ts_version[0]}")
        
        # Database size
        cur.execute("""
            SELECT pg_database_size(current_database()) as size,
                   pg_size_pretty(pg_database_size(current_database())) as pretty_size
        """)
        db_size = cur.fetchone()
        click.echo(f"Database Size: {db_size[1]}")
        
        # Connection count
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        conn_count = cur.fetchone()[0]
        click.echo(f"Active Connections: {conn_count}")
        
        # Table count
        cur.execute("""
            SELECT count(*) FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        table_count = cur.fetchone()[0]
        click.echo(f"Tables: {table_count}")
        
        conn.close()
        click.echo("\nDatabase is running and healthy!")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
def metrics():
    """Show database metrics"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Top tables by size
        click.echo("\n=== Top Tables by Size ===")
        cur.execute("""
            SELECT 
                schemaname || '.' || tablename as table_name,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 10
        """)
        
        tables = cur.fetchall()
        click.echo(tabulate(tables, headers=['Table', 'Size'], tablefmt='grid'))
        
        # Hypertable statistics
        click.echo("\n=== Hypertable Statistics ===")
        cur.execute("""
            SELECT 
                hypertable_name,
                to_char(total_bytes/1024/1024, 'FM999,999') || ' MB' as total_size,
                number_of_chunks
            FROM timescaledb_information.hypertable
        """)
        
        hypertables = cur.fetchall()
        if hypertables:
            click.echo(tabulate(hypertables, headers=['Hypertable', 'Total Size', 'Chunks'], tablefmt='grid'))
        
        # Recent metrics count
        click.echo("\n=== Recent Metrics (Last 24h) ===")
        cur.execute("""
            SELECT 
                'device_metrics' as table_name,
                count(*) as count
            FROM metrics.device_metrics
            WHERE time > NOW() - INTERVAL '24 hours'
            UNION ALL
            SELECT 
                'network_metrics',
                count(*)
            FROM metrics.network_metrics
            WHERE time > NOW() - INTERVAL '24 hours'
            UNION ALL
            SELECT 
                'gpu_metrics',
                count(*)
            FROM metrics.gpu_metrics
            WHERE time > NOW() - INTERVAL '24 hours'
        """)
        
        metrics = cur.fetchall()
        click.echo(tabulate(metrics, headers=['Metric Type', 'Count'], tablefmt='grid'))
        
        conn.close()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
def backup():
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{os.environ['SNAP_DATA']}/backups/networkdb_backup_{timestamp}.sql"
        
        click.echo(f"Creating backup: {backup_file}")
        
        # Create backup directory if it doesn't exist
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        
        # Run pg_dump
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PARAMS['password']
        
        result = subprocess.run([
            'pg_dump',
            '-h', DB_PARAMS['host'],
            '-p', DB_PARAMS['port'],
            '-U', DB_PARAMS['user'],
            '-d', DB_PARAMS['database'],
            '-f', backup_file,
            '--verbose'
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Get file size
            size = os.path.getsize(backup_file)
            size_mb = size / 1024 / 1024
            click.echo(f"Backup completed successfully!")
            click.echo(f"File: {backup_file}")
            click.echo(f"Size: {size_mb:.2f} MB")
        else:
            click.echo(f"Backup failed: {result.stderr}", err=True)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.argument('backup_file')
def restore(backup_file):
    """Restore database from backup"""
    try:
        if not os.path.exists(backup_file):
            click.echo(f"Backup file not found: {backup_file}", err=True)
            return
            
        if not click.confirm(f"This will restore the database from {backup_file}. Continue?"):
            return
            
        click.echo(f"Restoring from: {backup_file}")
        
        # Run pg_restore or psql depending on file format
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PARAMS['password']
        
        result = subprocess.run([
            'psql',
            '-h', DB_PARAMS['host'],
            '-p', DB_PARAMS['port'],
            '-U', DB_PARAMS['user'],
            '-d', DB_PARAMS['database'],
            '-f', backup_file
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            click.echo("Restore completed successfully!")
        else:
            click.echo(f"Restore failed: {result.stderr}", err=True)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
def vacuum():
    """Run VACUUM ANALYZE on all tables"""
    try:
        click.echo("Running VACUUM ANALYZE...")
        conn = get_connection()
        conn.set_isolation_level(0)  # AUTOCOMMIT
        cur = conn.cursor()
        
        # Get all tables
        cur.execute("""
            SELECT schemaname, tablename 
            FROM pg_tables 
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        """)
        
        tables = cur.fetchall()
        for schema, table in tables:
            click.echo(f"Vacuuming {schema}.{table}...")
            cur.execute(f'VACUUM ANALYZE "{schema}"."{table}"')
            
        click.echo("VACUUM ANALYZE completed!")
        conn.close()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
def init():
    """Initialize database schema"""
    try:
        click.echo("Initializing database schema...")
        
        # Run init SQL script
        init_script = f"{os.environ['SNAP']}/etc/init-db.sql"
        if os.path.exists(init_script):
            env = os.environ.copy()
            env['PGPASSWORD'] = DB_PARAMS['password']
            
            result = subprocess.run([
                'psql',
                '-h', DB_PARAMS['host'],
                '-p', DB_PARAMS['port'],
                '-U', DB_PARAMS['user'],
                '-d', DB_PARAMS['database'],
                '-f', init_script
            ], env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                click.echo("Database schema initialized successfully!")
            else:
                click.echo(f"Initialization failed: {result.stderr}", err=True)
        else:
            click.echo("Init script not found!", err=True)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

if __name__ == '__main__':
    cli()