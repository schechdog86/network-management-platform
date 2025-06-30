# Snap Distribution System

Enterprise snap distribution and rollout management for Ubuntu Core devices.

## Overview

The Snap Distribution System provides enterprise-grade snap package distribution with progressive rollouts, health monitoring, and rollback capabilities. It integrates with snap store proxies for caching and bandwidth optimization.

## Features

### 🚀 Rollout Strategies
- **Immediate**: Deploy to all devices immediately
- **Progressive**: Deploy in configurable phases (e.g., 10% → 30% → 70% → 100%)
- **Canary**: Small subset deployment followed by full rollout
- **Scheduled**: Time-based deployment schedules

### 🛡️ Safety & Monitoring
- Automatic rollback on failure threshold breach
- Real-time health monitoring
- Manual approval gates between phases
- Comprehensive error tracking and logging

### 📦 Store Proxy Integration
- Snap Store Proxy support for caching
- Bandwidth optimization
- Offline deployment capabilities
- Revision pinning and control

### 🎯 Targeting & Control
- Device group targeting
- Include/exclude device lists
- Multi-environment support
- Channel-based distribution

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Management    │────│  Snap Store      │────│   Canonical     │
│   Platform      │    │  Proxy           │    │   Snap Store    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│  Distribution   │    │    Cache &       │
│   Service       │    │   Bandwidth      │
└─────────────────┘    │  Optimization    │
         │              └──────────────────┘
         │
         ▼
┌─────────────────┐
│   Target        │
│   Devices       │
│  (Ubuntu Core)  │
└─────────────────┘
```

## Quick Start

### 1. Register Store Proxy (Optional)

```bash
curl -X POST "http://localhost:8000/api/v1/snap-distribution/store-proxy/register" \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_id": "main-proxy",
    "endpoint": "https://snap-proxy.example.com",
    "auth_token": "optional-auth-token"
  }'
```

### 2. Create Progressive Distribution

```bash
curl -X POST "http://localhost:8000/api/v1/snap-distribution/distributions" \
  -H "Content-Type: application/json" \
  -d '{
    "snap_name": "firefox",
    "source_channel": {
      "track": "latest",
      "risk": "candidate"
    },
    "target_channel": {
      "track": "latest", 
      "risk": "stable"
    },
    "target_devices": ["device-1", "device-2", "device-3"],
    "rollout_policy": {
      "strategy": "progressive",
      "phases": [10, 30, 70, 100],
      "phase_duration_hours": 24,
      "rollback_threshold_percent": 5.0,
      "health_check_enabled": true,
      "approval_required": false
    }
  }'
```

### 3. Monitor Distribution

```bash
# List all distributions
curl "http://localhost:8000/api/v1/snap-distribution/distributions"

# Get specific distribution status
curl "http://localhost:8000/api/v1/snap-distribution/distributions/{distribution_id}"
```

### 4. Control Distribution

```bash
# Pause distribution
curl -X POST "http://localhost:8000/api/v1/snap-distribution/distributions/{distribution_id}/pause"

# Resume distribution
curl -X POST "http://localhost:8000/api/v1/snap-distribution/distributions/{distribution_id}/resume"

# Rollback distribution
curl -X POST "http://localhost:8000/api/v1/snap-distribution/distributions/{distribution_id}/rollback"
```

## Configuration

### Environment Variables

```bash
# Snap Store Proxy (optional)
SNAP_STORE_PROXY_ENDPOINT=https://snap-proxy.example.com
SNAP_STORE_PROXY_AUTH_TOKEN=your-token

# Distribution Settings
SNAP_DISTRIBUTION_MAX_CONCURRENT=10
SNAP_DISTRIBUTION_HEALTH_CHECK_INTERVAL=300
SNAP_DISTRIBUTION_CLEANUP_DAYS=7
```

### Rollout Policy Configuration

```yaml
rollout_policy:
  strategy: "progressive"           # immediate, progressive, canary, scheduled
  phases: [10, 30, 70, 100]        # Rollout percentages
  phase_duration_hours: 24         # Hours between phases
  rollback_threshold_percent: 5.0  # Auto-rollback threshold
  health_check_enabled: true       # Enable health monitoring
  approval_required: false         # Manual approval gates
  target_groups:                   # Include device groups
    - "production"
    - "staging"
  exclude_groups:                  # Exclude device groups
    - "development"
    - "maintenance"
```

## Snap Store Proxy Setup

### Prerequisites

- Ubuntu 18.04+ or Ubuntu Core
- PostgreSQL database
- Domain name with TLS certificate
- Network connectivity to Canonical's store

### Installation

```bash
# Install snap-store-proxy snap
sudo snap install snap-store-proxy

# Configure database
sudo snap set snap-store-proxy \
  database.host=localhost \
  database.name=snap_proxy \
  database.user=snap_proxy \
  database.password=secure_password

# Configure domain
sudo snap set snap-store-proxy \
  domain=snap-proxy.example.com \
  tls.cert=/path/to/cert.pem \
  tls.key=/path/to/key.pem

# Start services
sudo snap start snap-store-proxy
```

### Device Configuration

Configure devices to use the proxy:

```bash
# On each Ubuntu Core device
sudo snap set core proxy.store=https://snap-proxy.example.com
```

## Security Considerations

### Access Control
- Use authentication tokens for proxy access
- Implement role-based access for distribution operations
- Audit all distribution activities

### Network Security
- Use TLS for all communications
- Implement network segmentation
- Monitor network traffic for anomalies

### Snap Security
- Verify snap signatures
- Use strict confinement
- Monitor snap permissions and interfaces

## Monitoring & Alerting

### Health Metrics
- Distribution success/failure rates
- Device update status
- Network bandwidth usage
- Proxy cache hit rates

### Alerts
- Failed distributions above threshold
- Device communication failures
- Proxy service outages
- Storage capacity warnings

### Logging
- All distribution operations
- Device communication attempts
- Proxy access logs
- Security events

## Troubleshooting

### Common Issues

#### Distribution Stuck in Progress
```bash
# Check distribution status
curl "http://localhost:8000/api/v1/snap-distribution/distributions/{id}"

# Check device connectivity
curl "http://localhost:8000/api/v1/snapd/devices/{device_id}/health"

# Force pause and investigate
curl -X POST "http://localhost:8000/api/v1/snap-distribution/distributions/{id}/pause"
```

#### High Failure Rate
```bash
# Check distribution logs
curl "http://localhost:8000/api/v1/snap-distribution/distributions/{id}/logs"

# Check individual device logs
curl "http://localhost:8000/api/v1/snapd/devices/{device_id}/changes"

# Consider rollback
curl -X POST "http://localhost:8000/api/v1/snap-distribution/distributions/{id}/rollback"
```

#### Proxy Connection Issues
```bash
# Test proxy connectivity
curl -I https://snap-proxy.example.com/v2/system-info

# Check proxy logs
sudo snap logs snap-store-proxy

# Verify proxy configuration
sudo snap get snap-store-proxy
```

### Debug Mode

Enable verbose logging:

```bash
export SNAP_DISTRIBUTION_LOG_LEVEL=DEBUG
export SNAPD_DEBUG=1
```

## Best Practices

### 1. Staging Environment
- Always test distributions in staging first
- Use canary deployments for critical updates
- Maintain parallel staging infrastructure

### 2. Rollout Strategy
- Start with small percentages (5-10%)
- Monitor health metrics closely
- Set appropriate rollback thresholds
- Use approval gates for production

### 3. Device Groups
- Organize devices by environment
- Use geographic groupings
- Consider hardware differences
- Implement maintenance windows

### 4. Monitoring
- Set up comprehensive alerting
- Monitor device health continuously
- Track distribution metrics
- Maintain audit logs

### 5. Backup & Recovery
- Maintain snap backups
- Test rollback procedures
- Document recovery processes
- Train operations team

## API Reference

### Distribution Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/distributions` | GET | List distributions |
| `/distributions` | POST | Create distribution |
| `/distributions/{id}` | GET | Get distribution status |
| `/distributions/{id}/pause` | POST | Pause distribution |
| `/distributions/{id}/resume` | POST | Resume distribution |
| `/distributions/{id}/rollback` | POST | Rollback distribution |
| `/distributions/{id}/logs` | GET | Get distribution logs |

### Store Proxy Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/store-proxy/register` | POST | Register proxy |
| `/store-proxy/list` | GET | List proxies |
| `/store-proxy/{id}/status` | GET | Get proxy status |

### Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/channels/available` | GET | List channels |
| `/rollout-strategies` | GET | List strategies |
| `/health` | GET | Service health |

## Integration Examples

### Python SDK

```python
from snap_distribution_client import SnapDistributionClient

client = SnapDistributionClient("http://localhost:8000")

# Create progressive distribution
distribution = client.create_distribution(
    snap_name="firefox",
    source_channel="latest/candidate",
    target_channel="latest/stable",
    target_devices=["device-1", "device-2"],
    strategy="progressive",
    phases=[10, 50, 100]
)

# Monitor progress
status = client.get_distribution_status(distribution.id)
print(f"Progress: {status.progress_percent}%")
```

### CI/CD Integration

```yaml
# GitLab CI example
deploy_snap:
  stage: deploy
  script:
    - |
      curl -X POST "$DISTRIBUTION_API/distributions" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d @distribution-config.json
  only:
    - main
```

## Support

- **Documentation**: [https://docs.example.com/snap-distribution](https://docs.example.com/snap-distribution)
- **Issues**: [GitHub Issues](https://github.com/example/network-management-platform/issues)
- **Community**: [Discord/Slack Channel](https://discord.gg/example)

## License

This project is licensed under the MIT License - see the LICENSE file for details.