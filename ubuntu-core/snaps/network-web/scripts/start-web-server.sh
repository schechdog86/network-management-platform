#!/bin/bash
set -e

# Network Management Web Interface Startup Script

# Create necessary directories
mkdir -p $SNAP_DATA/logs
mkdir -p $SNAP_DATA/cache
mkdir -p $SNAP_DATA/uploads

# Copy runtime configuration
cp $SNAP/app/runtime-config.js $SNAP_DATA/

# Update API endpoint if configured
if [ -n "$REACT_APP_API_URL" ]; then
    echo "window._env_ = { API_URL: '$REACT_APP_API_URL' };" > $SNAP_DATA/runtime-config.js
fi

# Check if API is available
echo "Checking API connection..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/v1/health > /dev/null; then
        echo "API is available!"
        break
    fi
    echo "Waiting for API... ($i/30)"
    sleep 2
done

# Start the web server using serve
cd $SNAP/app

# Log startup
echo "Starting Network Management Web Interface on port $PORT"
echo "API URL: $REACT_APP_API_URL"

# Use serve for production static file serving
exec serve -s . -l $PORT -c $SNAP/etc/serve.json