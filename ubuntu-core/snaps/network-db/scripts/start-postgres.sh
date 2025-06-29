#!/bin/bash
set -e

# PostgreSQL + TimescaleDB Startup Script

# Create necessary directories
mkdir -p $PGDATA
mkdir -p $SNAP_DATA/postgresql/run
mkdir -p $SNAP_DATA/postgresql/conf
mkdir -p $SNAP_DATA/postgresql/log
mkdir -p $SNAP_DATA/backups

# Copy configuration files if they don't exist
if [ ! -f "$SNAP_DATA/postgresql/conf/postgresql.conf" ]; then
    cp $SNAP/etc/postgresql.conf $SNAP_DATA/postgresql/conf/
fi

if [ ! -f "$SNAP_DATA/postgresql/conf/pg_hba.conf" ]; then
    cp $SNAP/etc/pg_hba.conf $SNAP_DATA/postgresql/conf/
fi

# Initialize database if needed
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL database..."
    
    # Initialize the database
    /usr/lib/postgresql/16/bin/initdb -D $PGDATA \
        --locale=C.UTF-8 \
        --encoding=UTF8 \
        --username=$POSTGRES_USER
    
    # Update configuration
    echo "shared_preload_libraries = 'timescaledb'" >> $PGDATA/postgresql.conf
    echo "timescaledb.telemetry_level = off" >> $PGDATA/postgresql.conf
    
    # Start PostgreSQL temporarily to run initial setup
    /usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l $SNAP_DATA/postgresql/log/startup.log start
    
    # Wait for PostgreSQL to start
    sleep 5
    
    # Create user and database
    /usr/lib/postgresql/16/bin/psql -U $POSTGRES_USER postgres <<EOF
ALTER USER $POSTGRES_USER PASSWORD '$POSTGRES_PASSWORD';
CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;
\c $POSTGRES_DB
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS postgis;
EOF

    # Run initialization script
    if [ -f "$SNAP/etc/init-db.sql" ]; then
        /usr/lib/postgresql/16/bin/psql -U $POSTGRES_USER $POSTGRES_DB < $SNAP/etc/init-db.sql
    fi
    
    # Stop PostgreSQL
    /usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA stop
    
    echo "Database initialization complete"
fi

# Configure runtime settings
cat > $PGDATA/postgresql.conf <<EOF
# Network Management Database Configuration
listen_addresses = 'localhost'
port = 5432
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '$SNAP_DATA/postgresql/log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_line_prefix = '%m [%p] %u@%d '
log_statement = 'mod'
log_duration = off

# TimescaleDB
shared_preload_libraries = 'timescaledb'
timescaledb.telemetry_level = off
timescaledb.max_background_workers = 8

# Performance
cpu_tuple_cost = 0.003
cpu_index_tuple_cost = 0.001
cpu_operator_cost = 0.0005

# Replication (for future use)
wal_level = replica
archive_mode = on
archive_command = 'test ! -f $SNAP_DATA/backups/%f && cp %p $SNAP_DATA/backups/%f'
max_wal_senders = 3
EOF

# Configure authentication
cat > $PGDATA/pg_hba.conf <<EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     peer
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             10.0.0.0/8              md5
host    all             all             172.16.0.0/12           md5
host    all             all             192.168.0.0/16          md5
EOF

# Create socket directory for content interface
SOCKET_DIR=$SNAP_DATA/postgresql
mkdir -p $SOCKET_DIR

# Start PostgreSQL
echo "Starting PostgreSQL..."
exec /usr/lib/postgresql/16/bin/postgres \
    -D $PGDATA \
    -k $SOCKET_DIR \
    -c config_file=$PGDATA/postgresql.conf \
    -c hba_file=$PGDATA/pg_hba.conf