# Inter-Snap Communication Guide

## Overview

This guide explains how the different snaps in the Network Management Platform communicate with each other using Ubuntu Core's content interfaces.

## Snap Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   network-web   │────▶│ network-manager │────▶│   network-db    │
│  (React UI)     │     │ (FastAPI Server)│     │  (PostgreSQL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         │                       ▼                        │
         │              ┌─────────────────┐               │
         └─────────────▶│    ray-head     │◀──────────────┘
                        │ (AI Orchestrator)│
                        └─────────────────┘
                                 │
                        ┌────────▼────────┐
                        │   ai-worker     │
                        │  (GPU Workers)  │
                        └─────────────────┘
```

## Content Interfaces

### 1. Database Connection (network-db)

**Slot (Provider):** `network-db`
```yaml
slots:
  postgres-socket:
    interface: content
    content: postgres-socket
    write:
      - $SNAP_DATA/postgresql
```

**Plug (Consumer):** `network-manager-server`
```yaml
plugs:
  postgres-db:
    interface: content
    content: postgres-socket
    target: $SNAP_DATA/postgres
```

**Usage:**
```python
# In network-manager-server
DATABASE_URL = f"postgresql://user:pass@{SNAP_DATA}/postgres/.s.PGSQL.5432/networkdb"
```

### 2. API Connection (network-manager-server)

**Slot (Provider):** `network-manager-server`
```yaml
slots:
  network-manager-api:
    interface: content
    content: network-manager-api
    read:
      - $SNAP_DATA/api
```

**Plug (Consumer):** `network-web`, `ray-head`
```yaml
plugs:
  api-connection:
    interface: content
    content: network-manager-api
    target: $SNAP_DATA/api
```

### 3. Ray Cluster Connection (ray-head)

**Slot (Provider):** `ray-head`
```yaml
slots:
  ray-cluster:
    interface: content
    content: ray-cluster
    write:
      - $SNAP_DATA/cluster
```

**Plug (Consumer):** `ai-worker`
```yaml
plugs:
  ray-cluster:
    interface: content
    content: ray-cluster
    target: $SNAP_DATA/ray-cluster
```

## Connection Setup

### Install and Connect Snaps

```bash
# Install all snaps
sudo snap install network-db
sudo snap install network-manager-server
sudo snap install network-web
sudo snap install ray-head
sudo snap install ai-worker

# Connect interfaces
# Database connections
sudo snap connect network-manager-server:postgres-db network-db:postgres-socket
sudo snap connect ray-head:postgres-db network-db:postgres-socket

# API connections
sudo snap connect network-web:api-connection network-manager-server:network-manager-api
sudo snap connect ray-head:network-api network-manager-server:network-manager-api

# Ray cluster connections
sudo snap connect ai-worker:ray-cluster ray-head:ray-cluster

# Redis connections (if using shared Redis)
sudo snap connect network-manager-server:redis-cache network-db:redis-socket
```

## Communication Patterns

### 1. Web UI → API Server

The web interface communicates with the API server via HTTP REST API:

```javascript
// In React app
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const fetchDevices = async () => {
  const response = await fetch(`${API_URL}/api/v1/devices`);
  return response.json();
};
```

### 2. API Server → Database

The API server uses SQLAlchemy with async PostgreSQL connection:

```python
# Using Unix socket from content interface
DATABASE_URL = f"postgresql+asyncpg://netmanager:password@/{POSTGRES_DB}?host={SNAP_DATA}/postgres"

engine = create_async_engine(DATABASE_URL)
```

### 3. API Server → Ray Head

The API server submits jobs to Ray cluster:

```python
import ray

# Connect to Ray cluster
ray.init(address=f"ray://{RAY_HEAD_IP}:6379")

# Submit job
@ray.remote
def process_network_scan(subnet):
    # Job logic
    pass

future = process_network_scan.remote("192.168.1.0/24")
result = ray.get(future)
```

### 4. Ray Head → Workers

Ray head automatically manages worker connections:

```python
# Workers read cluster address from content interface
with open(f"{SNAP_DATA}/ray-cluster/address") as f:
    ray_address = f.read().strip()

ray.init(address=ray_address)
```

## Shared Data Access

### 1. Backup Storage

All snaps can access shared backup location:

```yaml
layout:
  /var/lib/network-manager/backups:
    bind: $SNAP_COMMON/backups
```

### 2. Metrics Export

Prometheus metrics are exposed via HTTP endpoints:

- API Server: `http://localhost:8000/metrics`
- Ray Dashboard: `http://localhost:8265/metrics`
- Database: `http://localhost:9187/metrics` (postgres_exporter)

## Security Considerations

### 1. Interface Auto-Connection

For production, request auto-connections in snapcraft.yaml:

```yaml
apps:
  api-server:
    plugs:
      - network
      - network-bind
    slots:
      - network-manager-api
    
plugs:
  postgres-db:
    interface: content
    content: postgres-socket
    default-provider: network-db
```

### 2. Authentication Between Services

- **API Authentication**: JWT tokens shared via environment variables
- **Database Auth**: PostgreSQL passwords in snap configuration
- **Ray Auth**: Optional Redis password for cluster security

### 3. Network Isolation

Snaps communicate over localhost by default. For distributed deployment:

```bash
# Configure API server for external access
sudo snap set network-manager-server api-host=0.0.0.0

# Configure Ray for multi-node
sudo snap set ray-head ray-head-ip=10.0.0.10
```

## Testing Inter-Snap Communication

### 1. Test Database Connection

```bash
# From network-manager-server snap
network-manager-server.netctl db-test

# Check logs
sudo journalctl -u snap.network-manager-server.api-server
```

### 2. Test API Connection

```bash
# From network-web snap
network-web.webctl healthcheck

# Test API endpoint
curl http://localhost:8000/api/v1/health
```

### 3. Test Ray Cluster

```bash
# Check Ray status
ray-head.rayctl status

# Submit test job
ray-head.ray-cli submit test-job.py
```

## Troubleshooting

### Connection Refused

1. Check if all services are running:
```bash
snap services
```

2. Verify interface connections:
```bash
snap connections network-manager-server
```

3. Check bind addresses:
```bash
sudo ss -tlnp | grep -E "5432|8000|6379|8265"
```

### Permission Denied

1. Ensure interfaces are connected:
```bash
sudo snap connect <consumer>:<plug> <provider>:<slot>
```

2. Check AppArmor denials:
```bash
sudo journalctl -t audit | grep DENIED
```

### Performance Issues

1. Monitor resource usage:
```bash
snap run --shell network-manager-server
htop
```

2. Check content interface overhead:
```bash
# Compare socket vs TCP performance
pgbench -h /var/snap/network-db/current/postgresql ...
```

## Best Practices

1. **Use Content Interfaces for Local Communication**: More secure and efficient than network interfaces
2. **Implement Health Checks**: Each snap should verify its dependencies are available
3. **Handle Connection Failures Gracefully**: Implement retry logic with exponential backoff
4. **Monitor Interface Performance**: Use Prometheus metrics to track latency
5. **Document Interface Changes**: Version your interfaces and maintain compatibility

## Example: Complete Integration Test

```python
#!/usr/bin/env python3
"""
Test inter-snap communication
"""

import asyncio
import httpx
import asyncpg
import ray

async def test_integration():
    # Test database connection
    db_conn = await asyncpg.connect(
        host="/var/snap/network-manager-server/current/postgres",
        database="networkdb",
        user="netmanager"
    )
    db_version = await db_conn.fetchval("SELECT version()")
    print(f"✓ Database: {db_version}")
    await db_conn.close()
    
    # Test API connection
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/health")
        print(f"✓ API: {response.json()}")
    
    # Test Ray connection
    ray.init(address="auto")
    print(f"✓ Ray: {len(ray.nodes())} nodes")
    ray.shutdown()
    
    # Test web interface
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:3000")
        print(f"✓ Web UI: {response.status_code}")
    
    print("\n✓ All services are connected and working!")

if __name__ == "__main__":
    asyncio.run(test_integration())
```

This completes the inter-snap communication setup and testing.