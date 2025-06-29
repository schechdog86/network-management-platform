// Device management store using Zustand

import { create } from 'zustand';
import { Device, DeviceMetric, NetworkScan } from '@/types';
import { apiService } from '@/services/api';

interface DeviceState {
  devices: Device[];
  selectedDevice: Device | null;
  deviceMetrics: Record<string, DeviceMetric[]>;
  networkScans: NetworkScan[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  fetchDevices: (params?: any) => Promise<void>;
  fetchDevice: (deviceId: string) => Promise<void>;
  addDevice: (device: Partial<Device>) => Promise<boolean>;
  updateDevice: (deviceId: string, device: Partial<Device>) => Promise<boolean>;
  deleteDevice: (deviceId: string) => Promise<boolean>;
  setSelectedDevice: (device: Device | null) => void;
  
  // Device metrics
  fetchDeviceMetrics: (deviceId: string, metricType?: string, hours?: number) => Promise<void>;
  
  // Device actions
  wakeDevice: (deviceId: string) => Promise<boolean>;
  rebootDevice: (deviceId: string) => Promise<boolean>;
  
  // Network scanning
  startNetworkScan: (subnets: string[], scanType?: string) => Promise<string | null>;
  fetchScanStatus: (scanId: string) => Promise<void>;
  
  // Real-time updates
  updateDeviceFromWebSocket: (deviceData: any) => void;
  
  // Utility
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useDeviceStore = create<DeviceState>()((set, get) => ({
  devices: [],
  selectedDevice: null,
  deviceMetrics: {},
  networkScans: [],
  isLoading: false,
  error: null,

  fetchDevices: async (params = {}) => {
    set({ isLoading: true, error: null });
    
    try {
      const devices = await apiService.getDevices(params);
      set({ devices, isLoading: false });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to fetch devices';
      set({ error: errorMessage, isLoading: false });
    }
  },

  fetchDevice: async (deviceId: string) => {
    set({ isLoading: true, error: null });
    
    try {
      const device = await apiService.getDevice(deviceId);
      set({ selectedDevice: device, isLoading: false });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to fetch device';
      set({ error: errorMessage, isLoading: false });
    }
  },

  addDevice: async (device: Partial<Device>) => {
    set({ isLoading: true, error: null });
    
    try {
      const newDevice = await apiService.createDevice(device);
      const { devices } = get();
      set({ 
        devices: [...devices, newDevice], 
        isLoading: false 
      });
      return true;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to create device';
      set({ error: errorMessage, isLoading: false });
      return false;
    }
  },

  updateDevice: async (deviceId: string, device: Partial<Device>) => {
    set({ isLoading: true, error: null });
    
    try {
      const updatedDevice = await apiService.updateDevice(deviceId, device);
      const { devices, selectedDevice } = get();
      
      const newDevices = devices.map(d => 
        d.id === deviceId ? updatedDevice : d
      );
      
      set({ 
        devices: newDevices,
        selectedDevice: selectedDevice?.id === deviceId ? updatedDevice : selectedDevice,
        isLoading: false 
      });
      return true;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to update device';
      set({ error: errorMessage, isLoading: false });
      return false;
    }
  },

  deleteDevice: async (deviceId: string) => {
    set({ isLoading: true, error: null });
    
    try {
      await apiService.deleteDevice(deviceId);
      const { devices, selectedDevice } = get();
      
      const newDevices = devices.filter(d => d.id !== deviceId);
      
      set({ 
        devices: newDevices,
        selectedDevice: selectedDevice?.id === deviceId ? null : selectedDevice,
        isLoading: false 
      });
      return true;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to delete device';
      set({ error: errorMessage, isLoading: false });
      return false;
    }
  },

  setSelectedDevice: (device: Device | null) => {
    set({ selectedDevice: device });
  },

  fetchDeviceMetrics: async (deviceId: string, metricType?: string, hours = 24) => {
    try {
      const metrics = await apiService.getDeviceMetrics(deviceId, metricType, hours);
      const { deviceMetrics } = get();
      
      set({
        deviceMetrics: {
          ...deviceMetrics,
          [deviceId]: metrics
        }
      });
    } catch (error: any) {
      console.error('Failed to fetch device metrics:', error);
      // Don't set error state for metrics - they're not critical
    }
  },

  wakeDevice: async (deviceId: string) => {
    try {
      const result = await apiService.wakeDevice(deviceId);
      return result.success || false;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to wake device';
      set({ error: errorMessage });
      return false;
    }
  },

  rebootDevice: async (deviceId: string) => {
    try {
      const result = await apiService.rebootDevice(deviceId);
      return result.success || false;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to reboot device';
      set({ error: errorMessage });
      return false;
    }
  },

  startNetworkScan: async (subnets: string[], scanType = 'ping') => {
    set({ isLoading: true, error: null });
    
    try {
      const scan = await apiService.startNetworkScan(subnets, scanType);
      const { networkScans } = get();
      
      set({ 
        networkScans: [...networkScans, scan],
        isLoading: false 
      });
      
      return scan.id;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to start network scan';
      set({ error: errorMessage, isLoading: false });
      return null;
    }
  },

  fetchScanStatus: async (scanId: string) => {
    try {
      const scan = await apiService.getScanStatus(scanId);
      const { networkScans } = get();
      
      const newScans = networkScans.map(s => 
        s.id === scanId ? scan : s
      );
      
      set({ networkScans: newScans });
    } catch (error: any) {
      console.error('Failed to fetch scan status:', error);
    }
  },

  updateDeviceFromWebSocket: (deviceData: any) => {
    const { devices } = get();
    
    // Update device if it exists, otherwise add it
    const existingIndex = devices.findIndex(d => d.id === deviceData.id);
    
    if (existingIndex >= 0) {
      const newDevices = [...devices];
      newDevices[existingIndex] = { ...newDevices[existingIndex], ...deviceData };
      set({ devices: newDevices });
    } else {
      // New device discovered
      set({ devices: [...devices, deviceData] });
    }
  },

  clearError: () => set({ error: null }),
  
  setLoading: (loading: boolean) => set({ isLoading: loading })
}));