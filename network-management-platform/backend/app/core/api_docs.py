"""
API Documentation Configuration and Custom Examples
"""

from typing import Dict, Any

# API Metadata
API_TITLE = "Network Management Platform API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
## 🚀 Network Management Platform API

Enterprise-grade network management platform with AI automation, GPU acceleration, and distributed computing capabilities.

### 🔑 Authentication

This API uses **JWT Bearer tokens** for authentication. To access protected endpoints:

1. Call `/api/v1/auth/login` with your credentials
2. Use the returned `access_token` in the Authorization header: `Bearer <token>`
3. Tokens expire after 30 minutes by default

### 📚 Main Features

- **Device Management**: CRUD operations for network devices
- **Network Discovery**: Automated scanning and device detection
- **System Metrics**: Real-time monitoring and historical data
- **SNMP Monitoring**: Multi-device concurrent monitoring
- **SSH Management**: Secure remote command execution
- **Wake-on-LAN**: Remote power management
- **Backup Management**: Automated backup with ZFS/Restic
- **PXE Boot**: Network boot and OS deployment
- **AI Chat**: Natural language system management
- **Predictive Maintenance**: AI-powered health predictions

### 🔧 WebSocket Support

Real-time updates are available via WebSocket at `/ws`. Subscribe to channels:
- `device_updates`: Device status changes
- `system_metrics`: Live system metrics
- `alerts`: System alerts and notifications

### 📊 Rate Limiting

API endpoints are rate-limited to ensure fair usage:
- Authentication: 5 requests per minute
- General endpoints: 100 requests per minute
- Bulk operations: 10 requests per minute

### 🛠️ Error Handling

The API uses standard HTTP status codes:
- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

Error responses include a detail message:
```json
{
  "detail": "Error description"
}
```
"""

# API Tags metadata
TAGS_METADATA = [
    {
        "name": "auth",
        "description": "Authentication operations - login, token refresh, user management",
    },
    {
        "name": "devices",
        "description": "Device management - CRUD operations, metrics, actions",
    },
    {
        "name": "network",
        "description": "Network discovery and scanning operations",
    },
    {
        "name": "metrics",
        "description": "System metrics collection and retrieval",
    },
    {
        "name": "snmp",
        "description": "SNMP monitoring and management",
    },
    {
        "name": "ssh",
        "description": "SSH session management and command execution",
    },
    {
        "name": "wake-on-lan",
        "description": "Wake-on-LAN operations for remote power management",
    },
    {
        "name": "backup",
        "description": "Backup management with ZFS snapshots and Restic",
    },
    {
        "name": "pxe",
        "description": "PXE boot server and deployment management",
    },
    {
        "name": "ai",
        "description": "AI-powered features - chat, predictions, automation",
    },
    {
        "name": "websocket",
        "description": "WebSocket connections for real-time updates",
    },
    {
        "name": "health",
        "description": "Health check and system status endpoints",
    },
]

# OpenAPI examples
API_EXAMPLES: Dict[str, Any] = {
    "login": {
        "request": {
            "username": "admin",
            "password": "admin123"
        },
        "response": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
    },
    "device": {
        "create": {
            "ip_address": "192.168.1.100",
            "hostname": "server-01",
            "device_type": "server",
            "vendor": "Dell",
            "snmp_enabled": True,
            "snmp_community": "public",
            "ssh_enabled": True,
            "ssh_username": "admin"
        },
        "response": {
            "id": 1,
            "ip_address": "192.168.1.100",
            "hostname": "server-01",
            "mac_address": "00:11:22:33:44:55",
            "device_type": "server",
            "vendor": "Dell",
            "status": "online",
            "last_seen": "2024-01-01T12:00:00Z",
            "snmp_enabled": True,
            "ssh_enabled": True,
            "created_at": "2024-01-01T12:00:00Z"
        }
    },
    "network_scan": {
        "request": {
            "subnets": ["192.168.1.0/24"],
            "scan_type": "detailed"
        },
        "response": {
            "id": "scan-123",
            "subnets": ["192.168.1.0/24"],
            "scan_type": "detailed",
            "status": "in_progress",
            "progress": 45,
            "discovered_devices": 12
        }
    },
    "metrics": {
        "current": {
            "timestamp": "2024-01-01T12:00:00Z",
            "hostname": "netmgmt-server",
            "platform": "Linux",
            "cpu": {
                "usage_percent": 25.5,
                "count_physical": 4,
                "count_logical": 8
            },
            "memory": {
                "virtual": {
                    "total": 16777216000,
                    "available": 8388608000,
                    "percent": 50.0
                }
            }
        }
    }
}

# Custom OpenAPI schema
def custom_openapi_schema(app):
    """Generate custom OpenAPI schema with examples"""
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=TAGS_METADATA,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter: Bearer <JWT token>"
        }
    }
    
    # Add examples to components
    openapi_schema["components"]["examples"] = API_EXAMPLES
    
    # Add servers
    openapi_schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://api.networkplatform.io", "description": "Production server"}
    ]
    
    # Add external docs
    openapi_schema["externalDocs"] = {
        "description": "Network Management Platform Documentation",
        "url": "https://docs.networkplatform.io"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema