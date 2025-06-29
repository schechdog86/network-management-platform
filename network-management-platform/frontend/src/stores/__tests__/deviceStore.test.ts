import { act, renderHook } from '@testing-library/react';
import { useDeviceStore } from '../deviceStore';
import { apiService } from '@/services/api';
import { Device } from '@/types';

// Mock the API service
jest.mock('@/services/api', () => ({
  apiService: {
    getDevices: jest.fn(),
    getDevice: jest.fn(),
    createDevice: jest.fn(),
    updateDevice: jest.fn(),
    deleteDevice: jest.fn(),
    wakeDevice: jest.fn(),
    rebootDevice: jest.fn(),
    startNetworkScan: jest.fn(),
    getScanStatus: jest.fn(),
  },
}));

describe('deviceStore', () => {
  const mockDevices: Device[] = [
    {
      id: '1',
      hostname: 'device1',
      ip_address: '192.168.1.1',
      mac_address: '00:11:22:33:44:55',
      status: 'online',
      device_type: 'server',
      last_seen: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: '2',
      hostname: 'device2',
      ip_address: '192.168.1.2',
      mac_address: '00:11:22:33:44:66',
      status: 'offline',
      device_type: 'workstation',
      last_seen: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset store state before each test
    useDeviceStore.setState({
      devices: [],
      selectedDevice: null,
      deviceMetrics: {},
      networkScans: [],
      isLoading: false,
      error: null,
    });
  });

  describe('fetchDevices', () => {
    it('should fetch devices successfully', async () => {
      (apiService.getDevices as jest.Mock).mockResolvedValue(mockDevices);

      const { result } = renderHook(() => useDeviceStore());

      expect(result.current.isLoading).toBe(false);
      expect(result.current.devices).toEqual([]);

      await act(async () => {
        await result.current.fetchDevices();
      });

      expect(apiService.getDevices).toHaveBeenCalledWith({});
      expect(result.current.devices).toEqual(mockDevices);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe(null);
    });

    it('should handle fetch error', async () => {
      const error = new Error('Network error');
      (apiService.getDevices as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useDeviceStore());

      await act(async () => {
        await result.current.fetchDevices();
      });

      expect(result.current.devices).toEqual([]);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe('Network error');
    });

    it('should handle loading states correctly', async () => {
      (apiService.getDevices as jest.Mock).mockResolvedValue(mockDevices);

      const { result } = renderHook(() => useDeviceStore());

      // Initial state
      expect(result.current.isLoading).toBe(false);

      // Fetch devices
      await act(async () => {
        await result.current.fetchDevices();
      });

      // After completion, loading should be false and devices should be loaded
      expect(result.current.isLoading).toBe(false);
      expect(result.current.devices).toEqual(mockDevices);
    });
  });

  describe('addDevice', () => {
    it('should add a new device', async () => {
      const newDevice = { ...mockDevices[0], id: '3' };
      (apiService.createDevice as jest.Mock).mockResolvedValue(newDevice);

      const { result } = renderHook(() => useDeviceStore());
      
      // Set initial devices
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      let success = false;
      await act(async () => {
        success = await result.current.addDevice({
          hostname: newDevice.hostname,
          ip_address: newDevice.ip_address,
          mac_address: newDevice.mac_address,
          device_type: newDevice.device_type,
        });
      });

      expect(success).toBe(true);
      expect(apiService.createDevice).toHaveBeenCalledWith({
        hostname: newDevice.hostname,
        ip_address: newDevice.ip_address,
        mac_address: newDevice.mac_address,
        device_type: newDevice.device_type,
      });
      expect(result.current.devices).toHaveLength(3);
      expect(result.current.devices[2]).toEqual(newDevice);
    });

    it('should handle add error', async () => {
      const error = new Error('Failed to add device');
      (apiService.createDevice as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      let success = false;
      await act(async () => {
        success = await result.current.addDevice({
          hostname: 'new-device',
          ip_address: '192.168.1.100',
          mac_address: '00:11:22:33:44:77',
          device_type: 'server',
        });
      });

      expect(success).toBe(false);
      expect(result.current.devices).toHaveLength(2); // No device added
      expect(result.current.error).toBe('Failed to add device');
    });
  });

  describe('updateDevice', () => {
    it('should update an existing device', async () => {
      const updatedDevice = { ...mockDevices[0], hostname: 'updated-device' };
      (apiService.updateDevice as jest.Mock).mockResolvedValue(updatedDevice);

      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      let success = false;
      await act(async () => {
        success = await result.current.updateDevice('1', { hostname: 'updated-device' });
      });

      expect(success).toBe(true);
      expect(apiService.updateDevice).toHaveBeenCalledWith('1', { hostname: 'updated-device' });
      expect(result.current.devices[0].hostname).toBe('updated-device');
    });

    it('should handle update error', async () => {
      const error = new Error('Update failed');
      (apiService.updateDevice as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      let success = false;
      await act(async () => {
        success = await result.current.updateDevice('1', { hostname: 'updated-device' });
      });

      expect(success).toBe(false);
      expect(result.current.devices[0].hostname).toBe('device1'); // Not updated
      expect(result.current.error).toBe('Update failed');
    });
  });

  describe('deleteDevice', () => {
    it('should delete a device', async () => {
      (apiService.deleteDevice as jest.Mock).mockResolvedValue(true);

      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      let success = false;
      await act(async () => {
        success = await result.current.deleteDevice('1');
      });

      expect(success).toBe(true);
      expect(apiService.deleteDevice).toHaveBeenCalledWith('1');
      expect(result.current.devices).toHaveLength(1);
      expect(result.current.devices[0].id).toBe('2');
    });

    it('should handle delete error', async () => {
      const error = new Error('Delete failed');
      (apiService.deleteDevice as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      let success = false;
      await act(async () => {
        success = await result.current.deleteDevice('1');
      });

      expect(success).toBe(false);
      expect(result.current.devices).toHaveLength(2); // Not deleted
      expect(result.current.error).toBe('Delete failed');
    });
  });

  describe('updateDeviceFromWebSocket', () => {
    it('should update device from WebSocket data', () => {
      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      const wsUpdate = {
        id: '1',
        status: 'offline' as const,
        last_seen: new Date().toISOString(),
      };

      act(() => {
        result.current.updateDeviceFromWebSocket(wsUpdate);
      });

      expect(result.current.devices[0].status).toBe('offline');
      expect(result.current.devices[0].last_seen).toBe(wsUpdate.last_seen);
    });

    it('should add new device if not exists from WebSocket', () => {
      const { result } = renderHook(() => useDeviceStore());
      
      act(() => {
        useDeviceStore.setState({ devices: [...mockDevices] });
      });

      const wsUpdate = {
        id: '999',
        status: 'online' as const,
      };

      act(() => {
        result.current.updateDeviceFromWebSocket(wsUpdate);
      });

      // Based on the implementation, it adds the device if not found
      expect(result.current.devices).toHaveLength(3);
      expect(result.current.devices[2].id).toBe('999');
    });
  });

  describe('device actions', () => {
    it('should wake a device', async () => {
      (apiService.wakeDevice as jest.Mock).mockResolvedValue({ success: true });

      const { result } = renderHook(() => useDeviceStore());

      let success = false;
      await act(async () => {
        success = await result.current.wakeDevice('1');
      });

      expect(success).toBe(true);
      expect(apiService.wakeDevice).toHaveBeenCalledWith('1');
    });

    it('should reboot a device', async () => {
      (apiService.rebootDevice as jest.Mock).mockResolvedValue({ success: true });

      const { result } = renderHook(() => useDeviceStore());

      let success = false;
      await act(async () => {
        success = await result.current.rebootDevice('1');
      });

      expect(success).toBe(true);
      expect(apiService.rebootDevice).toHaveBeenCalledWith('1');
    });

  });

  describe('network scanning', () => {
    it('should start a network scan', async () => {
      const scanId = 'scan-123';
      const mockScan = { 
        id: scanId,
        subnets: ['192.168.1.0/24'],
        status: 'in_progress',
        created_at: new Date().toISOString()
      };
      (apiService.startNetworkScan as jest.Mock).mockResolvedValue(mockScan);

      const { result } = renderHook(() => useDeviceStore());

      let resultScanId: string | null = null;
      await act(async () => {
        resultScanId = await result.current.startNetworkScan(['192.168.1.0/24']);
      });

      expect(resultScanId).toBe(scanId);
      expect(apiService.startNetworkScan).toHaveBeenCalledWith(['192.168.1.0/24'], 'ping');
      expect(result.current.networkScans).toHaveLength(1);
      expect(result.current.networkScans[0]).toEqual(mockScan);
    });

    it('should handle scan error', async () => {
      const error = new Error('Scan failed');
      (apiService.startNetworkScan as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useDeviceStore());

      let resultScanId: string | null = null;
      await act(async () => {
        resultScanId = await result.current.startNetworkScan(['192.168.1.0/24']);
      });

      expect(resultScanId).toBe(null);
      expect(result.current.error).toBe('Scan failed');
    });
  });
});