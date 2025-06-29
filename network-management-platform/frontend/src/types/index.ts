// Type definitions for the Network Management Platform

export interface Device {
  id: string;
  ip_address: string;
  hostname?: string;
  mac_address?: string;
  device_type?: string;
  vendor?: string;
  status: 'online' | 'offline' | 'unknown';
  last_seen: string;
  snmp_enabled?: boolean;
  snmp_community?: string;
  snmp_version?: number;
  snmp_port?: number;
  snmp_timeout?: number;
  ssh_enabled?: boolean;
  ssh_port?: number;
  ssh_username?: string;
  created_at: string;
  updated_at: string;
}

export interface DeviceMetric {
  id: string;
  device_id: string;
  metric_type: string;
  value: number;
  unit: string;
  timestamp: string;
  metadata?: Record<string, string | number | boolean>;
}

export interface SystemMetrics {
  timestamp: string;
  hostname: string;
  platform: string;
  cpu: {
    usage_percent: number;
    usage_per_core: number[];
    count_physical: number;
    count_logical: number;
    frequency?: {
      current: number;
      min: number;
      max: number;
    };
  };
  memory: {
    virtual: {
      total: number;
      available: number;
      used: number;
      free: number;
      percent: number;
    };
    swap: {
      total: number;
      used: number;
      free: number;
      percent: number;
    };
  };
  disk: {
    partitions: Array<{
      device: string;
      mountpoint: string;
      filesystem: string;
      total: number;
      used: number;
      free: number;
      percent: number;
    }>;
    io: {
      read_count: number;
      write_count: number;
      read_bytes: number;
      write_bytes: number;
    };
  };
  network: {
    total_io: {
      bytes_sent: number;
      bytes_recv: number;
      packets_sent: number;
      packets_recv: number;
    };
    interfaces: Record<string, NetworkInterface>;
  };
  system?: {
    uptime_seconds: number;
    boot_time: number;
    users: number;
  };
}

export interface NetworkInterface {
  addresses: Array<{
    family: string;
    address: string;
    netmask?: string;
    broadcast?: string;
  }>;
  stats: {
    isup: boolean;
    duplex: string;
    speed: number;
    mtu: number;
  };
  io?: {
    bytes_sent: number;
    bytes_recv: number;
    packets_sent: number;
    packets_recv: number;
    errin: number;
    errout: number;
    dropin: number;
    dropout: number;
  };
}

export interface NetworkScan {
  id: string;
  network: string;
  scan_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  devices_found: number;
  started_at: string;
  completed_at?: string;
  error?: string;
}

export interface SnmpData {
  device_id: string;
  timestamp: string;
  system_info?: {
    hostname?: string;
    description?: string;
    uptime?: number;
    contact?: string;
    location?: string;
  };
  interfaces: Array<{
    index: number;
    name: string;
    description: string;
    oper_status: number;
    in_octets: number;
    out_octets: number;
    in_errors: number;
    out_errors: number;
  }>;
  cpu_usage?: number;
  memory_usage?: {
    total: number;
    used: number;
    free: number;
    usage_percent: number;
  };
}

export interface WebSocketMessage {
  type: 'device_update' | 'system_metrics' | 'snmp_data' | 'alert' | 'heartbeat' | 'connection_status' | 'error' | 'pxe_boot' | 'backups';
  data?: {
    type?: string;
    [key: string]: unknown;
  };
  device_id?: string;
  timestamp: string;
}

export interface Alert {
  id: string;
  type: 'warning' | 'error' | 'info' | 'success';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  device_id?: string;
  timestamp: string;
  acknowledged?: boolean;
}

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in?: number;
}

export interface DashboardStats {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  active_scans: number;
  active_alerts: number;
  system_uptime: number;
  cpu_usage: number;
  memory_usage: number;
  network_throughput: {
    sent: number;
    received: number;
  };
}

export interface ChartDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface ChartConfig {
  type: 'line' | 'bar' | 'doughnut' | 'pie';
  data: {
    labels: string[];
    datasets: Array<{
      label: string;
      data: number[];
      backgroundColor?: string | string[];
      borderColor?: string;
      borderWidth?: number;
      fill?: boolean;
    }>;
  };
  options?: {
    responsive?: boolean;
    maintainAspectRatio?: boolean;
    plugins?: {
      legend?: { display?: boolean; position?: string };
      title?: { display?: boolean; text?: string };
      tooltip?: { enabled?: boolean; mode?: string };
    };
    scales?: Record<string, unknown>;
  };
}

// WebSocket connection states
export type WebSocketState = 'connecting' | 'connected' | 'disconnected' | 'error';

// API response wrapper
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

// Pagination
export interface PaginationParams {
  skip?: number;
  limit?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

// PXE Boot Types
export interface PXEServerStatus {
  status: 'running' | 'stopped' | 'error';
  services: {
    dhcp: 'running' | 'stopped';
    tftp: 'running' | 'stopped';
    http: 'running' | 'stopped';
  };
  config?: PXEServerConfig;
}

export interface PXEServerConfig {
  interface: string;
  subnet: string;
  tftp_server: string;
  http_server: string;
  boot_mode: 'bios' | 'uefi' | 'both';
}

export interface PXEDeploymentJob {
  id: string;
  target_mac: string;
  os_type: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  started_at: string;
  completed_at?: string;
  error?: string;
}

export interface DHCPReservation {
  mac_address: string;
  ip_address: string;
  hostname?: string;
  created_at: string;
}

export interface DHCPLease {
  mac_address: string;
  ip_address: string;
  hostname?: string;
  expires_at: string;
  state: 'active' | 'expired';
}

// Settings Types
export type SettingsValue = string | number | boolean | string[];

export interface Settings {
  [key: string]: SettingsValue;
}

// Metrics Collection Status
export interface MetricsCollectionStatus {
  is_running: boolean;
  interval: number;
  last_collection: string;
  collections_count: number;
  error_count: number;
}

// Error types
export interface ErrorResponse {
  detail: string;
  status_code?: number;
  timestamp?: string;
}

// Chat Types
export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  status?: 'sending' | 'sent' | 'error';
  entities?: Record<string, string | number | boolean>;
  result?: unknown;
}

export interface ChatContext {
  device_count: number;
  active_alerts: number;
  system_status: string;
}