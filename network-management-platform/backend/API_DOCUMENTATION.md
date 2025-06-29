# Network Management Platform API Documentation

## Overview

The Network Management Platform provides a comprehensive RESTful API for managing network infrastructure, monitoring devices, and automating network operations. This document covers all available endpoints, authentication, and usage examples.

## Base URL

```
Development: http://localhost:8000/api/v1
Production: https://api.networkplatform.io/api/v1
```

## Authentication

The API uses JWT Bearer token authentication. All endpoints except `/auth/login` and `/health` require authentication.

### Getting a Token

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using the Token

Include the token in the Authorization header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## API Endpoints

### Authentication

#### Login
- **POST** `/api/v1/auth/login`
- **Description**: Authenticate user and receive access token
- **Body**: Form data with `username` and `password`
- **Response**: JWT token and token type

#### Get Current User
- **GET** `/api/v1/auth/me`
- **Description**: Get information about the authenticated user
- **Auth**: Required
- **Response**: User details

### Device Management

#### List Devices
- **GET** `/api/v1/devices`
- **Description**: Get paginated list of network devices
- **Auth**: Required
- **Query Parameters**:
  - `skip` (int): Number of records to skip (default: 0)
  - `limit` (int): Maximum records to return (default: 100, max: 1000)
  - `device_type` (string): Filter by type (router, switch, server, etc.)
  - `status` (string): Filter by status (online, offline, unknown)
- **Response**: Array of device objects

#### Get Device Details
- **GET** `/api/v1/devices/{device_id}`
- **Description**: Get detailed information about a specific device
- **Auth**: Required
- **Response**: Device object with all properties

#### Create Device
- **POST** `/api/v1/devices`
- **Description**: Add a new device to the network
- **Auth**: Required (Admin)
- **Body**:
```json
{
  "ip_address": "192.168.1.100",
  "hostname": "server-01",
  "device_type": "server",
  "vendor": "Dell",
  "snmp_enabled": true,
  "snmp_community": "public",
  "ssh_enabled": true,
  "ssh_username": "admin"
}
```

#### Update Device
- **PUT** `/api/v1/devices/{device_id}`
- **Description**: Update device properties
- **Auth**: Required (Admin)
- **Body**: Partial device object with fields to update

#### Delete Device
- **DELETE** `/api/v1/devices/{device_id}`
- **Description**: Remove a device from management
- **Auth**: Required (Admin)

#### Get Device Metrics
- **GET** `/api/v1/devices/{device_id}/metrics`
- **Description**: Get performance metrics for a device
- **Auth**: Required
- **Query Parameters**:
  - `metric_type` (string): Specific metric type to retrieve
  - `hours` (int): Number of hours of historical data (default: 24)
- **Response**: Array of metric data points

#### Wake Device
- **POST** `/api/v1/devices/{device_id}/wake`
- **Description**: Send Wake-on-LAN packet to device
- **Auth**: Required
- **Response**: Operation status

#### Reboot Device
- **POST** `/api/v1/devices/{device_id}/reboot`
- **Description**: Initiate device reboot via SSH
- **Auth**: Required (Admin)
- **Response**: Operation status

### Network Discovery

#### Start Network Scan
- **POST** `/api/v1/devices/scan`
- **Description**: Start network discovery scan
- **Auth**: Required
- **Body**:
```json
{
  "subnets": ["192.168.1.0/24"],
  "scan_type": "detailed"
}
```
- **Response**: Scan job details with ID

#### Get Scan Status
- **GET** `/api/v1/devices/scan/{scan_id}`
- **Description**: Check status of running scan
- **Auth**: Required
- **Response**: Scan progress and results

### System Metrics

#### Get Current Metrics
- **GET** `/api/v1/metrics/current`
- **Description**: Get current system performance metrics
- **Auth**: Required
- **Response**: CPU, memory, disk, and network statistics

#### Get Metrics History
- **GET** `/api/v1/metrics/history`
- **Description**: Get historical system metrics
- **Auth**: Required
- **Query Parameters**:
  - `hours` (int): Hours of history to retrieve (default: 1)
- **Response**: Array of metric snapshots

#### Start Metrics Collection
- **POST** `/api/v1/metrics/collection/start`
- **Description**: Start automatic metrics collection
- **Auth**: Required
- **Query Parameters**:
  - `interval` (int): Collection interval in seconds (default: 5)

#### Stop Metrics Collection
- **POST** `/api/v1/metrics/collection/stop`
- **Description**: Stop automatic metrics collection
- **Auth**: Required

### SNMP Monitoring

#### Test SNMP Connectivity
- **POST** `/api/v1/snmp/test`
- **Description**: Test SNMP connection to a device
- **Auth**: Required
- **Query Parameters**:
  - `ip_address` (string): Target device IP
  - `community` (string): SNMP community string (default: public)
  - `version` (int): SNMP version (default: 2)
  - `port` (int): SNMP port (default: 161)

#### Start SNMP Monitoring
- **POST** `/api/v1/snmp/monitor/{device_id}/start`
- **Description**: Start continuous SNMP monitoring for a device
- **Auth**: Required
- **Query Parameters**:
  - `interval` (int): Polling interval in seconds (default: 300)

#### Get SNMP Status
- **GET** `/api/v1/snmp/monitor/status`
- **Description**: Get status of all SNMP monitoring tasks
- **Auth**: Required

### SSH Management

#### Execute SSH Command
- **POST** `/api/v1/ssh/execute`
- **Description**: Execute command on remote device via SSH
- **Auth**: Required (Admin)
- **Body**:
```json
{
  "device_id": 1,
  "command": "show version",
  "timeout": 30
}
```

#### List SSH Sessions
- **GET** `/api/v1/ssh/sessions`
- **Description**: Get list of active SSH sessions
- **Auth**: Required

### Wake-on-LAN

#### Send Wake Packet
- **POST** `/api/v1/wake-on-lan/wake`
- **Description**: Send Wake-on-LAN packet
- **Auth**: Required
- **Body**:
```json
{
  "mac_address": "00:11:22:33:44:55",
  "ip_address": "192.168.1.100",
  "broadcast_ip": "255.255.255.255",
  "port": 9,
  "verify": true
}
```

#### Bulk Wake Devices
- **POST** `/api/v1/wake-on-lan/wake/bulk`
- **Description**: Wake multiple devices
- **Auth**: Required
- **Body**:
```json
{
  "devices": [
    {"mac_address": "00:11:22:33:44:55", "ip_address": "192.168.1.100"},
    {"mac_address": "00:11:22:33:44:56", "ip_address": "192.168.1.101"}
  ],
  "verify": true
}
```

### Backup Management

#### Create Backup Job
- **POST** `/api/v1/backup/jobs`
- **Description**: Create a new backup job
- **Auth**: Required
- **Body**:
```json
{
  "device_id": 1,
  "backup_type": "config",
  "destination": "local"
}
```

#### List Backup Jobs
- **GET** `/api/v1/backup/jobs`
- **Description**: Get list of backup jobs
- **Auth**: Required
- **Query Parameters**:
  - `status` (string): Filter by status
  - `device_id` (int): Filter by device

### PXE Boot Management

#### Start PXE Server
- **POST** `/api/v1/pxe/server/start`
- **Description**: Start PXE boot server
- **Auth**: Required (Admin)
- **Body**:
```json
{
  "interface": "eth0",
  "subnet": "192.168.100.0/24",
  "tftp_server": "192.168.100.1",
  "http_server": "http://192.168.100.1:8080",
  "boot_mode": "both"
}
```

#### Create Deployment
- **POST** `/api/v1/pxe/deployments`
- **Description**: Create OS deployment job
- **Auth**: Required (Admin)
- **Body**:
```json
{
  "target_mac": "00:11:22:33:44:55",
  "os_type": "ubuntu2204",
  "hostname": "server-01",
  "username": "admin",
  "password": "password123"
}
```

### AI Features

#### Chat with AI
- **POST** `/api/v1/ai/chat`
- **Description**: Send message to AI assistant
- **Auth**: Required
- **Body**:
```json
{
  "message": "Show me all offline devices"
}
```

#### Get Predictive Maintenance
- **POST** `/api/v1/ai/predictive-maintenance/analyze`
- **Description**: Analyze devices for maintenance predictions
- **Auth**: Required
- **Body**:
```json
{
  "device_ids": [1, 2, 3],
  "include_recommendations": true
}
```

### WebSocket

#### Connect to WebSocket
- **WS** `/ws`
- **Description**: Establish WebSocket connection for real-time updates
- **Auth**: Token passed as query parameter
- **Channels**:
  - `device_updates`: Device status changes
  - `system_metrics`: Live system metrics
  - `alerts`: System alerts
  - `pxe_boot`: PXE deployment updates
  - `backups`: Backup job progress

Example connection:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=your_jwt_token');

ws.onopen = () => {
  // Subscribe to channels
  ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['device_updates', 'alerts']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error description"
}
```

Common HTTP status codes:
- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

## Rate Limiting

API endpoints have the following rate limits:
- Authentication endpoints: 5 requests per minute
- General endpoints: 100 requests per minute per user
- Bulk operations: 10 requests per minute per user
- WebSocket connections: 5 concurrent connections per user

## Pagination

List endpoints support pagination using `skip` and `limit` parameters:
```
GET /api/v1/devices?skip=20&limit=10
```

Response includes pagination metadata in headers:
- `X-Total-Count`: Total number of items
- `X-Page-Count`: Total number of pages

## Filtering and Sorting

Many list endpoints support filtering and sorting:
```
GET /api/v1/devices?device_type=server&status=online&sort=hostname
```

## Best Practices

1. **Use pagination**: Always paginate large result sets
2. **Cache responses**: Implement client-side caching for frequently accessed data
3. **Handle errors gracefully**: Always check for error responses
4. **Use WebSocket for real-time data**: Don't poll endpoints for updates
5. **Respect rate limits**: Implement backoff strategies
6. **Keep tokens secure**: Never expose tokens in URLs or logs

## SDK and Client Libraries

Official SDKs are available for:
- Python: `pip install netmgmt-sdk`
- JavaScript/TypeScript: `npm install @netmgmt/sdk`
- Go: `go get github.com/netmgmt/go-sdk`

## Support

For API support and questions:
- Documentation: https://docs.networkplatform.io
- API Status: https://status.networkplatform.io
- Support Email: api-support@networkplatform.io