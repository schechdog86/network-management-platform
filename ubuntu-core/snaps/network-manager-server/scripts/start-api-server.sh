#!/bin/bash
set -e

# Network Manager Server - API Startup Script

# Wait for database
echo "Waiting for PostgreSQL..."
until pg_isready -h localhost -p 5432 -U netmanager; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is ready!"

# Run database migrations
cd $SNAP/app
alembic upgrade head

# Create directories
mkdir -p $SNAP_DATA/logs
mkdir -p $SNAP_DATA/uploads
mkdir -p $SNAP_DATA/backups
mkdir -p $SNAP_DATA/api

# Export API socket for content interface
echo "unix:$SNAP_DATA/api/api.sock" > $SNAP_DATA/api/socket

# Start FastAPI server
exec uvicorn app.main:app \
    --host $API_HOST \
    --port $API_PORT \
    --workers $UVICORN_WORKERS \
    --log-level $UVICORN_LOG_LEVEL \
    --access-log \
    --use-colors \
    --reload-dir $SNAP/app \
    --log-config $SNAP/etc/network-manager/logging.conf