#!/bin/bash
set -e

# Network Manager Server - Scheduler Startup Script

# Wait for services
echo "Waiting for Redis..."
until redis-cli -h localhost ping; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done

echo "Redis is ready!"

# Start Celery beat scheduler
cd $SNAP/app
exec celery -A app.core.celery_app beat \
    --loglevel=info \
    --scheduler celery.beat:PersistentScheduler \
    --schedule=$SNAP_DATA/celerybeat-schedule.db