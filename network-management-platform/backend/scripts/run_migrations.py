#!/usr/bin/env python3
"""
Run database migrations using Alembic
"""

import subprocess
import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def run_migrations():
    """Run all pending migrations"""
    print("Running database migrations...")
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    try:
        # Run alembic upgrade
        result = subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Migrations completed successfully!")
            print(result.stdout)
        else:
            print("❌ Migration failed!")
            print(result.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        sys.exit(1)

def check_migration_status():
    """Check current migration status"""
    print("\nChecking migration status...")
    
    try:
        result = subprocess.run(
            ["python", "-m", "alembic", "current"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("Current migration status:")
            print(result.stdout)
        else:
            print("Failed to check migration status")
            print(result.stderr)
            
    except Exception as e:
        print(f"Error checking migration status: {e}")

def show_migration_history():
    """Show migration history"""
    print("\nMigration history:")
    
    try:
        result = subprocess.run(
            ["python", "-m", "alembic", "history"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("Failed to get migration history")
            print(result.stderr)
            
    except Exception as e:
        print(f"Error getting migration history: {e}")

if __name__ == "__main__":
    print("🚀 Network Management Platform - Database Migration Tool")
    print("=" * 60)
    
    # Check if we should show status only
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_migration_status()
        show_migration_history()
    else:
        run_migrations()
        check_migration_status()