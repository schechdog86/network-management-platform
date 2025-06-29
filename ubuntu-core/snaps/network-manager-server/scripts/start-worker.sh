#!/bin/bash
set -e

# Network Manager Server - Worker Startup Script

# Wait for services
echo "Waiting for Redis..."
until redis-cli -h localhost ping; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done

echo "Redis is ready!"

# Start Celery worker
cd $SNAP/app
exec celery -A app.core.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --queues=default,network_tasks,backup_tasks,monitoring \
    --hostname=worker@%h