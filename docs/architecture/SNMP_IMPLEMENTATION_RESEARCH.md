# SNMP Implementation Research for Network Management Platform

## Table of Contents
1. [SNMP Basics](#snmp-basics)
2. [Python Libraries](#python-libraries)
3. [Common SNMP Monitoring Use Cases](#common-snmp-monitoring-use-cases)
4. [SNMP Security Considerations](#snmp-security-considerations)
5. [SNMP Agent and Manager Components](#snmp-agent-and-manager-components)
6. [Ubuntu Core Integration](#ubuntu-core-integration)
7. [Production Best Practices](#production-best-practices)
8. [Current Implementation Analysis](#current-implementation-analysis)

## SNMP Basics

### SNMP Versions

#### SNMP v1 (1988)
- First version of the protocol
- Community-based security (plaintext passwords)
- Limited error handling
- 32-bit counters only
- **Status**: Deprecated, should not be used

#### SNMP v2c (1993)
- Improved error handling and performance
- 64-bit counters support
- Still uses community strings (plaintext)
- Most widely deployed version
- **Status**: Still common but insecure

#### SNMP v3 (1998)
- Strong authentication and encryption
- User-based Security Model (USM)
- View-based Access Control Model (VACM)
- Three security levels:
  - NoAuthNoPriv: No authentication, no privacy
  - AuthNoPriv: Authentication, no privacy
  - AuthPriv: Authentication and privacy
- **Status**: Recommended for production use

### MIBs (Management Information Bases)
- Hierarchical database of network objects
- Standard MIBs:
  - MIB-II (RFC 1213): Basic network statistics
  - HOST-RESOURCES-MIB: System resources
  - IF-MIB: Interface statistics
  - UCD-SNMP-MIB: Linux-specific metrics

### OIDs (Object Identifiers)
- Unique identifiers for MIB objects
- Hierarchical dotted notation (e.g., 1.3.6.1.2.1.1.1.0)
- Common base OIDs:
  - iso(1).org(3).dod(6).internet(1).mgmt(2).mib-2(1)

### SNMP Operations
- **GET**: Retrieve single value
- **GET-NEXT**: Retrieve next value in MIB tree
- **GET-BULK**: Retrieve multiple values (v2c+)
- **SET**: Modify value
- **TRAP**: Unsolicited notification (agent to manager)
- **INFORM**: Acknowledged notification (v2c+)

## Python Libraries

### 1. PySNMP (Recommended)
- **Status**: Actively maintained (revived 2022-2024)
- **Features**:
  - Pure Python implementation
  - Full SNMPv1/v2c/v3 support
  - Async/await support
  - MIB compilation and parsing
  - IPv6 support
- **Dependencies**: 
  - cryptography (for SNMPv3 encryption)
  - pyasn1
- **Current Version**: 7.x series
- **Installation**: `pip install pysnmp`

### 2. EasySNMP
- **Status**: C-based, faster than PySNMP
- **Features**:
  - Simple API
  - Good performance
  - Limited to basic operations
- **Limitations**:
  - Requires Net-SNMP libraries
  - Less flexible than PySNMP
- **Installation**: `pip install easysnmp`

### 3. python-netsnmp
- **Status**: Direct bindings to Net-SNMP
- **Features**:
  - High performance
  - Full Net-SNMP features
- **Limitations**:
  - Complex installation
  - Platform-specific issues
- **Installation**: Requires Net-SNMP development libraries

## Common SNMP Monitoring Use Cases

### System Information
```python
SYSTEM_OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',        # System description
    'sysObjectID': '1.3.6.1.2.1.1.2.0',     # System object ID
    'sysUpTime': '1.3.6.1.2.1.1.3.0',       # System uptime
    'sysContact': '1.3.6.1.2.1.1.4.0',      # System contact
    'sysName': '1.3.6.1.2.1.1.5.0',         # System name
    'sysLocation': '1.3.6.1.2.1.1.6.0',     # System location
    'sysServices': '1.3.6.1.2.1.1.7.0'      # System services
}
```

### CPU Monitoring
```python
CPU_OIDS = {
    # Linux (UCD-SNMP-MIB)
    'load1min': '1.3.6.1.4.1.2021.10.1.3.1',
    'load5min': '1.3.6.1.4.1.2021.10.1.3.2',
    'load15min': '1.3.6.1.4.1.2021.10.1.3.3',
    
    # HOST-RESOURCES-MIB
    'hrProcessorLoad': '1.3.6.1.2.1.25.3.3.1.2',
    
    # Cisco specific
    'cpmCPUTotal5min': '1.3.6.1.4.1.9.9.109.1.1.1.1.8'
}
```

### Memory Monitoring
```python
MEMORY_OIDS = {
    # Linux (UCD-SNMP-MIB)
    'memTotalSwap': '1.3.6.1.4.1.2021.4.3.0',
    'memAvailSwap': '1.3.6.1.4.1.2021.4.4.0',
    'memTotalReal': '1.3.6.1.4.1.2021.4.5.0',
    'memAvailReal': '1.3.6.1.4.1.2021.4.6.0',
    'memTotalFree': '1.3.6.1.4.1.2021.4.11.0',
    'memShared': '1.3.6.1.4.1.2021.4.13.0',
    'memBuffer': '1.3.6.1.4.1.2021.4.14.0',
    'memCached': '1.3.6.1.4.1.2021.4.15.0',
    
    # HOST-RESOURCES-MIB
    'hrMemorySize': '1.3.6.1.2.1.25.2.2',
    'hrStorageUsed': '1.3.6.1.2.1.25.2.3.1.6',
    'hrStorageSize': '1.3.6.1.2.1.25.2.3.1.5'
}
```

### Disk Monitoring
```python
DISK_OIDS = {
    # Linux (UCD-SNMP-MIB)
    'dskPath': '1.3.6.1.4.1.2021.9.1.2',        # Mount point
    'dskDevice': '1.3.6.1.4.1.2021.9.1.3',      # Device
    'dskTotal': '1.3.6.1.4.1.2021.9.1.6',       # Total size (KB)
    'dskAvail': '1.3.6.1.4.1.2021.9.1.7',       # Available (KB)
    'dskUsed': '1.3.6.1.4.1.2021.9.1.8',        # Used (KB)
    'dskPercent': '1.3.6.1.4.1.2021.9.1.9',     # Used percentage
    'dskPercentNode': '1.3.6.1.4.1.2021.9.1.10' # Inode percentage
}
```

### Network Interface Monitoring
```python
INTERFACE_OIDS = {
    # IF-MIB (Standard)
    'ifIndex': '1.3.6.1.2.1.2.2.1.1',
    'ifDescr': '1.3.6.1.2.1.2.2.1.2',
    'ifType': '1.3.6.1.2.1.2.2.1.3',
    'ifMtu': '1.3.6.1.2.1.2.2.1.4',
    'ifSpeed': '1.3.6.1.2.1.2.2.1.5',
    'ifPhysAddress': '1.3.6.1.2.1.2.2.1.6',
    'ifAdminStatus': '1.3.6.1.2.1.2.2.1.7',
    'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',
    'ifLastChange': '1.3.6.1.2.1.2.2.1.9',
    'ifInOctets': '1.3.6.1.2.1.2.2.1.10',
    'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',
    'ifInErrors': '1.3.6.1.2.1.2.2.1.14',
    'ifOutErrors': '1.3.6.1.2.1.2.2.1.20'
}
```

## SNMP Security Considerations

### SNMPv1/v2c Security Issues
1. **Community Strings**:
   - Transmitted in plaintext
   - Acts as password for device access
   - Default values often unchanged (public/private)
   - Vulnerable to sniffing and replay attacks

2. **Mitigation for v1/v2c**:
   - Use complex, unique community strings
   - Implement ACLs to restrict source IPs
   - Use VLANs to isolate management traffic
   - Consider VPN or IPsec tunnels

### SNMPv3 Security Features

#### Authentication Protocols
- **HMAC-MD5-96**: Legacy, avoid if possible
- **HMAC-SHA-96**: Minimum recommended
- **HMAC-SHA-224**: Better security
- **HMAC-SHA-256**: Recommended
- **HMAC-SHA-384**: High security
- **HMAC-SHA-512**: Maximum security

#### Encryption Protocols
- **DES**: 56-bit, deprecated, do not use
- **3DES**: 168-bit, legacy
- **AES-128**: Minimum recommended
- **AES-192**: Better security
- **AES-256**: Recommended for sensitive data

#### Security Levels
1. **noAuthNoPriv**: No security (avoid)
2. **authNoPriv**: Authentication only
3. **authPriv**: Authentication + Encryption (recommended)

### Best Practices
1. Always use SNMPv3 with authPriv
2. Use strong authentication (SHA-256+)
3. Use strong encryption (AES-256)
4. Implement proper user management
5. Regular password rotation
6. Monitor SNMP access logs
7. Disable unused SNMP services

## SNMP Agent and Manager Components

### SNMP Manager (Our Implementation)
The network management platform implements an SNMP manager with:

```python
class SNMPManager:
    """Advanced SNMP management and monitoring"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def get_system_info(self, device: SNMPDevice) -> Optional[SystemInfo]
    async def get_interfaces(self, device: SNMPDevice) -> List[InterfaceInfo]
    async def get_cpu_usage(self, device: SNMPDevice) -> Optional[float]
    async def get_memory_usage(self, device: SNMPDevice) -> Optional[Dict[str, int]]
    async def monitor_device(self, device: SNMPDevice, interval: int = 60)
```

### SNMP Agent Components
For devices being monitored:

1. **Standard SNMP Agent** (snmpd):
   - Responds to SNMP requests
   - Sends traps/informs
   - Implements access control
   - Manages MIB data

2. **Sub-agents**:
   - Extend standard agent functionality
   - Application-specific metrics
   - Custom MIB implementation

### Trap Receiver Implementation
```python
class SNMPTrapReceiver:
    """SNMP trap receiver for notifications"""
    
    def __init__(self, listen_address='0.0.0.0', port=162):
        self.listen_address = listen_address
        self.port = port
        
    async def start(self):
        """Start listening for SNMP traps"""
        # Configure transport
        transport = await asyncio.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.listen_address, self.port)
        )
        
    def process_trap(self, trap_data):
        """Process received SNMP trap"""
        # Parse trap
        # Store in database
        # Trigger alerts
        # Update device status
```

## Ubuntu Core Integration

### Snap Interfaces Required
For SNMP monitoring in Ubuntu Core snaps:

1. **network**: Basic network access
2. **network-bind**: To bind SNMP ports (161/162)
3. **network-observe**: To monitor network statistics
4. **system-observe**: For system metrics
5. **hardware-observe**: For hardware information
6. **process-control**: For process monitoring

### Snap Configuration
```yaml
# snapcraft.yaml
name: network-snmp-monitor
apps:
  snmp-manager:
    command: bin/snmp-manager
    daemon: simple
    plugs:
      - network
      - network-bind
      - network-observe
      - system-observe
      - hardware-observe

plugs:
  network:
  network-bind:
  network-observe:
  system-observe:
  hardware-observe:
```

### Interface Connections
```bash
# Manual connections required for privileged interfaces
sudo snap connect network-snmp-monitor:network-observe
sudo snap connect network-snmp-monitor:system-observe
sudo snap connect network-snmp-monitor:hardware-observe
```

### Considerations
1. **Confinement**: Strict confinement limits access
2. **Port Binding**: May need classic confinement for port 161/162
3. **File Access**: Limited to SNAP_DATA and SNAP_COMMON
4. **Inter-snap Communication**: Use content interface

## Production Best Practices

### Performance Optimization
1. **Bulk Operations**: Use GetBulk for multiple OIDs
2. **Caching**: Cache static values (system info)
3. **Connection Pooling**: Reuse SNMP sessions
4. **Async Operations**: Use asyncio for concurrent requests
5. **Rate Limiting**: Prevent overwhelming devices

### Monitoring Strategy
1. **Tiered Intervals**:
   - Critical metrics: 1-5 minutes
   - Performance metrics: 5-15 minutes
   - Capacity metrics: 15-60 minutes

2. **Smart Polling**:
   - Adaptive intervals based on change rate
   - Skip unchanged values
   - Prioritize critical devices

### Error Handling
1. **Timeouts**: Configure appropriate timeouts
2. **Retries**: Implement exponential backoff
3. **Fallback**: Try different SNMP versions
4. **Logging**: Comprehensive error logging
5. **Alerting**: Notify on persistent failures

### Scalability
1. **Distributed Polling**: Multiple collector nodes
2. **Queue-based**: Use message queues for tasks
3. **Database Optimization**: Time-series databases
4. **Data Retention**: Implement data lifecycle

### Security Hardening
1. **Firewall Rules**: Restrict SNMP ports
2. **VLANs**: Separate management network
3. **Encryption**: Use SNMPv3 authPriv
4. **Audit Logging**: Log all SNMP access
5. **Regular Updates**: Keep SNMP software updated

## Current Implementation Analysis

### Strengths
1. **Async Architecture**: Uses asyncio for scalability
2. **Comprehensive Monitoring**: CPU, memory, disk, interfaces
3. **Flexible Configuration**: Per-device settings
4. **WebSocket Integration**: Real-time updates
5. **Database Storage**: Persistent metrics storage

### Areas for Enhancement
1. **SNMPv3 Support**: Currently focused on v1/v2c
2. **Trap Handling**: No trap receiver implementation
3. **MIB Management**: Limited MIB compilation support
4. **Bulk Operations**: Could optimize with GetBulk
5. **Error Recovery**: Basic retry mechanisms

### Recommended Improvements

#### 1. Enhanced SNMPv3 Support
```python
@dataclass
class SNMPv3Device(SNMPDevice):
    """Extended device class for SNMPv3"""
    auth_protocol: str = "SHA256"  # MD5, SHA, SHA224, SHA256, SHA384, SHA512
    priv_protocol: str = "AES256"  # DES, 3DES, AES, AES192, AES256
    context_name: str = ""
    engine_id: Optional[str] = None
```

#### 2. Trap Receiver Service
```python
class SNMPTrapService:
    """SNMP trap receiver service"""
    
    async def start_trap_receiver(self):
        """Start SNMP trap listener"""
        # Implement trap receiver
        # Store traps in database
        # Trigger alerts based on trap type
```

#### 3. MIB Compiler Integration
```python
class MIBManager:
    """MIB compilation and management"""
    
    def compile_mib(self, mib_file: str):
        """Compile MIB to Python module"""
        # Use mibdump.py from pysnmp
        
    def load_compiled_mib(self, mib_name: str):
        """Load compiled MIB module"""
        # Dynamic import of compiled MIB
```

#### 4. Performance Monitoring
```python
class SNMPPerformanceMonitor:
    """Monitor SNMP polling performance"""
    
    def track_poll_duration(self, device_id: str, duration: float):
        """Track polling duration for optimization"""
        
    def calculate_optimal_interval(self, device_id: str):
        """Calculate optimal polling interval based on performance"""
```

## Conclusion

The current SNMP implementation provides a solid foundation for network monitoring. Key priorities for enhancement:

1. **Security**: Implement full SNMPv3 support with strong encryption
2. **Scalability**: Add distributed polling and bulk operations
3. **Features**: Implement trap receiver and MIB management
4. **Ubuntu Core**: Ensure proper snap interface configuration
5. **Production**: Follow best practices for performance and reliability

The existing async architecture and comprehensive monitoring capabilities provide an excellent base for building a production-ready SNMP monitoring solution.