// API service for communicating with the backend

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { 
  Device, 
  DeviceMetric, 
  SystemMetrics, 
  NetworkScan, 
  User, 
  AuthTokens,
  ApiResponse,
  PaginatedResponse,
  PaginationParams
} from '@/types';

class ApiService {
  private api: AxiosInstance;
  private baseURL = '/api/v1';

  constructor() {
    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          // Token expired, try to refresh or redirect to login
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Authentication
  async login(username: string, password: string): Promise<AuthTokens> {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await this.api.post<AuthTokens>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return response.data;
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.api.get<User>('/auth/me');
    return response.data;
  }

  // Devices
  async getDevices(params?: PaginationParams & { 
    device_type?: string; 
    status?: string; 
  }): Promise<Device[]> {
    const response = await this.api.get<Device[]>('/devices', { params });
    return response.data;
  }

  async getDevice(deviceId: string): Promise<Device> {
    const response = await this.api.get<Device>(`/devices/${deviceId}`);
    return response.data;
  }

  async createDevice(device: Partial<Device>): Promise<Device> {
    const response = await this.api.post<Device>('/devices', device);
    return response.data;
  }

  async updateDevice(deviceId: string, device: Partial<Device>): Promise<Device> {
    const response = await this.api.put<Device>(`/devices/${deviceId}`, device);
    return response.data;
  }

  async deleteDevice(deviceId: string): Promise<void> {
    await this.api.delete(`/devices/${deviceId}`);
  }

  async getDeviceMetrics(
    deviceId: string, 
    metricType?: string, 
    hours: number = 24
  ): Promise<DeviceMetric[]> {
    const response = await this.api.get<DeviceMetric[]>(
      `/devices/${deviceId}/metrics`,
      { params: { metric_type: metricType, hours } }
    );
    return response.data;
  }

  async wakeDevice(deviceId: string): Promise<ApiResponse<{ message: string }>> {
    const response = await this.api.post<ApiResponse<{ message: string }>>(`/devices/${deviceId}/wake`);
    return response.data;
  }

  async rebootDevice(deviceId: string): Promise<ApiResponse<{ message: string }>> {
    const response = await this.api.post<ApiResponse<{ message: string }>>(`/devices/${deviceId}/reboot`);
    return response.data;
  }

  // Network Discovery
  async startNetworkScan(subnets: string[], scanType: string = 'ping'): Promise<NetworkScan> {
    const response = await this.api.post<NetworkScan>('/devices/scan', {
      subnets,
      scan_type: scanType
    });
    return response.data;
  }

  async getScanStatus(scanId: string): Promise<NetworkScan> {
    const response = await this.api.get<NetworkScan>(`/devices/scan/${scanId}`);
    return response.data;
  }

  // System Metrics
  async getCurrentMetrics(): Promise<SystemMetrics> {
    const response = await this.api.get<SystemMetrics>('/metrics/current');
    return response.data;
  }

  async getMetricsHistory(hours: number = 1): Promise<{ metrics: SystemMetrics[] }> {
    const response = await this.api.get<{ metrics: SystemMetrics[] }>(
      '/metrics/history',
      { params: { hours } }
    );
    return response.data;
  }

  async getMetricsSummary(): Promise<any> {
    const response = await this.api.get('/metrics/summary');
    return response.data;
  }

  async startMetricsCollection(interval: number = 5): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>(
      '/metrics/collection/start',
      null,
      { params: { interval } }
    );
    return response.data;
  }

  async stopMetricsCollection(): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>('/metrics/collection/stop');
    return response.data;
  }

  async getMetricsCollectionStatus(): Promise<any> {
    const response = await this.api.get('/metrics/collection/status');
    return response.data;
  }

  // SNMP Monitoring
  async testSnmpConnectivity(
    ipAddress: string,
    community: string = 'public',
    version: number = 2,
    port: number = 161
  ): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>('/snmp/test', null, {
      params: { ip_address: ipAddress, community, version, port }
    });
    return response.data;
  }

  async startSnmpMonitoring(deviceId: string, interval: number = 300): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>(
      `/snmp/monitor/${deviceId}/start`,
      null,
      { params: { interval } }
    );
    return response.data;
  }

  async stopSnmpMonitoring(deviceId: string): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>(`/snmp/monitor/${deviceId}/stop`);
    return response.data;
  }

  async getSnmpMonitoringStatus(deviceId?: string): Promise<any> {
    const url = deviceId ? `/snmp/monitor/${deviceId}/status` : '/snmp/monitor/status';
    const response = await this.api.get(url);
    return response.data;
  }

  async getSnmpEnabledDevices(): Promise<Device[]> {
    const response = await this.api.get<{ devices: Device[] }>('/snmp/devices/snmp-enabled');
    return response.data.devices;
  }

  // Wake-on-LAN
  async sendWakePacket(
    macAddress: string,
    ipAddress?: string,
    broadcastIp: string = '255.255.255.255',
    port: number = 9,
    verify: boolean = false
  ): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>('/wake-on-lan/wake', {
      mac_address: macAddress,
      ip_address: ipAddress,
      broadcast_ip: broadcastIp,
      port,
      verify
    });
    return response.data;
  }

  async sendMultipleWakePackets(
    macAddress: string,
    ipAddress?: string,
    broadcastIps: string[] = ['255.255.255.255'],
    ports: number[] = [9, 7],
    verify: boolean = false,
    verifyTimeout: number = 30
  ): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>('/wake-on-lan/wake/multiple', {
      mac_address: macAddress,
      ip_address: ipAddress,
      broadcast_ips: broadcastIps,
      ports,
      verify,
      verify_timeout: verifyTimeout
    });
    return response.data;
  }

  async bulkWakeDevices(devices: Array<{ mac_address: string; ip_address?: string }>, verify: boolean = false): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>('/wake-on-lan/wake/bulk', {
      devices,
      verify
    });
    return response.data;
  }

  async verifyDeviceWake(ipAddress: string, timeout: number = 30): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>(
      `/wake-on-lan/verify/${ipAddress}`,
      null,
      { params: { timeout } }
    );
    return response.data;
  }

  async getWakeHistory(macAddress?: string): Promise<any> {
    const response = await this.api.get('/wake-on-lan/history', {
      params: macAddress ? { mac_address: macAddress } : {}
    });
    return response.data;
  }

  async getSuggestedBroadcastIps(): Promise<{ suggested_broadcast_ips: string[]; recommended_ports: number[] }> {
    const response = await this.api.get('/wake-on-lan/broadcast-ips');
    return response.data;
  }

  // WebSocket Stats
  async getWebSocketStats(): Promise<any> {
    const response = await this.api.get('/websocket/ws/stats');
    return response.data;
  }

  async broadcastTestMessage(message: string = 'Test message'): Promise<ApiResponse<any>> {
    const response = await this.api.post<ApiResponse<any>>(
      '/websocket/ws/broadcast/test',
      null,
      { params: { message } }
    );
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.api.get('/health');
    return response.data;
  }

  // Generic HTTP methods for backward compatibility
  async get<T = any>(url: string, config?: any): Promise<{ data: T }> {
    return this.api.get(url, config);
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    return this.api.post(url, data, config);
  }

  async put<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    return this.api.put(url, data, config);
  }

  async delete<T = any>(url: string, config?: any): Promise<{ data: T }> {
    return this.api.delete(url, config);
  }
}

export const apiService = new ApiService();
export const api = apiService; // Backward compatibility
export default apiService;