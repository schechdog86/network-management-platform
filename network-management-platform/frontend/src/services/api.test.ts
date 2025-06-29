import axios from 'axios';
import { apiService } from './api';

jest.mock('axios');

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock as any;

// Mock window.location
delete (window as any).location;
window.location = { href: '' } as any;

describe('ApiService', () => {
  let mockedAxios: jest.Mocked<typeof axios>;
  let mockAxiosInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
    window.location.href = '';

    // Setup axios mock
    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() },
      },
    };

    mockedAxios = axios as jest.Mocked<typeof axios>;
    mockedAxios.create.mockReturnValue(mockAxiosInstance);
  });

  describe('initialization', () => {
    it('creates axios instance with correct config', () => {
      expect(mockedAxios.create).toHaveBeenCalledWith({
        baseURL: '/api/v1',
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    });

    it('sets up request interceptor', () => {
      expect(mockAxiosInstance.interceptors.request.use).toHaveBeenCalled();
    });

    it('sets up response interceptor', () => {
      expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalled();
    });
  });

  describe('authentication methods', () => {
    it('login sends correct form data', async () => {
      const mockTokens = { access_token: 'test-token', token_type: 'bearer' };
      mockAxiosInstance.post.mockResolvedValue({ data: mockTokens });

      const result = await apiService.login('testuser', 'password123');

      expect(mockAxiosInstance.post).toHaveBeenCalledWith(
        '/auth/login',
        expect.any(FormData),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );
      expect(result).toEqual(mockTokens);
    });

    it('getCurrentUser makes correct API call', async () => {
      const mockUser = { id: 1, username: 'testuser', email: 'test@example.com' };
      mockAxiosInstance.get.mockResolvedValue({ data: mockUser });

      const result = await apiService.getCurrentUser();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/auth/me');
      expect(result).toEqual(mockUser);
    });
  });

  describe('device methods', () => {
    const mockDevice = {
      id: '1',
      name: 'Test Device',
      ip_address: '192.168.1.1',
      device_type: 'router',
    };

    it('getDevices fetches all devices', async () => {
      const mockDevices = [mockDevice];
      mockAxiosInstance.get.mockResolvedValue({ data: mockDevices });

      const result = await apiService.getDevices();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/devices', { params: undefined });
      expect(result).toEqual(mockDevices);
    });

    it('getDevices with params', async () => {
      const mockDevices = [mockDevice];
      mockAxiosInstance.get.mockResolvedValue({ data: mockDevices });

      const params = { device_type: 'router', status: 'online' };
      const result = await apiService.getDevices(params);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/devices', { params });
      expect(result).toEqual(mockDevices);
    });

    it('getDevice fetches single device', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockDevice });

      const result = await apiService.getDevice('1');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/devices/1');
      expect(result).toEqual(mockDevice);
    });

    it('createDevice posts new device', async () => {
      mockAxiosInstance.post.mockResolvedValue({ data: mockDevice });

      const newDevice = { name: 'Test Device', ip_address: '192.168.1.1' };
      const result = await apiService.createDevice(newDevice);

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/devices', newDevice);
      expect(result).toEqual(mockDevice);
    });

    it('updateDevice updates existing device', async () => {
      mockAxiosInstance.put.mockResolvedValue({ data: mockDevice });

      const updates = { name: 'Updated Device' };
      const result = await apiService.updateDevice('1', updates);

      expect(mockAxiosInstance.put).toHaveBeenCalledWith('/devices/1', updates);
      expect(result).toEqual(mockDevice);
    });

    it('deleteDevice removes device', async () => {
      mockAxiosInstance.delete.mockResolvedValue({});

      await apiService.deleteDevice('1');

      expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/devices/1');
    });

    it('wakeDevice sends wake command', async () => {
      const mockResponse = { success: true, message: 'Wake packet sent' };
      mockAxiosInstance.post.mockResolvedValue({ data: mockResponse });

      const result = await apiService.wakeDevice('1');

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/devices/1/wake');
      expect(result).toEqual(mockResponse);
    });

    it('rebootDevice sends reboot command', async () => {
      const mockResponse = { success: true, message: 'Reboot initiated' };
      mockAxiosInstance.post.mockResolvedValue({ data: mockResponse });

      const result = await apiService.rebootDevice('1');

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/devices/1/reboot');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('network scanning', () => {
    it('startNetworkScan initiates scan', async () => {
      const mockScan = { id: 'scan-1', status: 'in_progress' };
      mockAxiosInstance.post.mockResolvedValue({ data: mockScan });

      const subnets = ['192.168.1.0/24'];
      const result = await apiService.startNetworkScan(subnets);

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/devices/scan', {
        subnets,
        scan_type: 'ping',
      });
      expect(result).toEqual(mockScan);
    });

    it('getScanStatus checks scan progress', async () => {
      const mockScan = { id: 'scan-1', status: 'completed' };
      mockAxiosInstance.get.mockResolvedValue({ data: mockScan });

      const result = await apiService.getScanStatus('scan-1');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/devices/scan/scan-1');
      expect(result).toEqual(mockScan);
    });
  });

  describe('system metrics', () => {
    it('getCurrentMetrics fetches current metrics', async () => {
      const mockMetrics = { cpu: 50, memory: 60 };
      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });

      const result = await apiService.getCurrentMetrics();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/metrics/current');
      expect(result).toEqual(mockMetrics);
    });

    it('getMetricsHistory fetches historical metrics', async () => {
      const mockHistory = { metrics: [{ cpu: 50 }, { cpu: 60 }] };
      mockAxiosInstance.get.mockResolvedValue({ data: mockHistory });

      const result = await apiService.getMetricsHistory(2);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/metrics/history', {
        params: { hours: 2 },
      });
      expect(result).toEqual(mockHistory);
    });
  });

  describe('interceptors', () => {
    let requestInterceptor: any;
    let responseInterceptor: any;

    beforeEach(() => {
      // Capture the interceptor functions
      requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0];
    });

    it('request interceptor adds auth token when available', () => {
      localStorageMock.getItem.mockReturnValue('test-token');

      const config = { headers: {} };
      const result = requestInterceptor(config);

      expect(config.headers.Authorization).toBe('Bearer test-token');
      expect(result).toBe(config);
    });

    it('request interceptor does not add token when not available', () => {
      localStorageMock.getItem.mockReturnValue(null);

      const config = { headers: {} };
      const result = requestInterceptor(config);

      expect(config.headers.Authorization).toBeUndefined();
      expect(result).toBe(config);
    });

    it('response interceptor handles 401 errors', async () => {
      const error = {
        response: { status: 401 },
      };

      const errorHandler = responseInterceptor[1];
      await expect(errorHandler(error)).rejects.toEqual(error);

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
      expect(window.location.href).toBe('/login');
    });

    it('response interceptor passes through other errors', async () => {
      const error = {
        response: { status: 500 },
      };

      const errorHandler = responseInterceptor[1];
      await expect(errorHandler(error)).rejects.toEqual(error);

      expect(localStorageMock.removeItem).not.toHaveBeenCalled();
      expect(window.location.href).toBe('');
    });
  });

  describe('wake-on-lan methods', () => {
    it('sendWakePacket sends wake packet', async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.post.mockResolvedValue({ data: mockResponse });

      const result = await apiService.sendWakePacket('AA:BB:CC:DD:EE:FF', '192.168.1.100');

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/wake-on-lan/wake', {
        mac_address: 'AA:BB:CC:DD:EE:FF',
        ip_address: '192.168.1.100',
        broadcast_ip: '255.255.255.255',
        port: 9,
        verify: false,
      });
      expect(result).toEqual(mockResponse);
    });

    it('bulkWakeDevices wakes multiple devices', async () => {
      const mockResponse = { success: true, results: [] };
      mockAxiosInstance.post.mockResolvedValue({ data: mockResponse });

      const devices = [
        { mac_address: 'AA:BB:CC:DD:EE:FF', ip_address: '192.168.1.100' },
        { mac_address: '11:22:33:44:55:66', ip_address: '192.168.1.101' },
      ];

      const result = await apiService.bulkWakeDevices(devices, true);

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/wake-on-lan/wake/bulk', {
        devices,
        verify: true,
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('health check', () => {
    it('performs health check', async () => {
      const mockHealth = { status: 'healthy' };
      mockAxiosInstance.get.mockResolvedValue({ data: mockHealth });

      const result = await apiService.healthCheck();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/health');
      expect(result).toEqual(mockHealth);
    });
  });
});