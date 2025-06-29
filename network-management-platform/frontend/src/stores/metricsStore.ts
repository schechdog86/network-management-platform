// System metrics store using Zustand

import { create } from 'zustand';
import { SystemMetrics, DashboardStats } from '@/types';
import { apiService } from '@/services/api';

interface MetricsState {
  currentMetrics: SystemMetrics | null;
  metricsHistory: SystemMetrics[];
  dashboardStats: DashboardStats | null;
  collectionStatus: any;
  isCollecting: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  fetchCurrentMetrics: () => Promise<void>;
  fetchMetricsHistory: (hours?: number) => Promise<void>;
  fetchCollectionStatus: () => Promise<void>;
  startCollection: (interval?: number) => Promise<boolean>;
  stopCollection: () => Promise<boolean>;
  
  // Real-time updates
  updateMetricsFromWebSocket: (metricsData: SystemMetrics) => void;
  
  // Dashboard
  calculateDashboardStats: () => void;
  
  // Utility
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useMetricsStore = create<MetricsState>()((set, get) => ({
  currentMetrics: null,
  metricsHistory: [],
  dashboardStats: null,
  collectionStatus: null,
  isCollecting: false,
  isLoading: false,
  error: null,

  fetchCurrentMetrics: async () => {
    try {
      const metrics = await apiService.getCurrentMetrics();
      set({ currentMetrics: metrics });
      get().calculateDashboardStats();
    } catch (error: any) {
      console.error('Failed to fetch current metrics:', error);
      // Don't set error state for background metrics fetching
    }
  },

  fetchMetricsHistory: async (hours = 1) => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiService.getMetricsHistory(hours);
      set({ 
        metricsHistory: response.metrics,
        isLoading: false 
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to fetch metrics history';
      set({ error: errorMessage, isLoading: false });
    }
  },

  fetchCollectionStatus: async () => {
    try {
      const status = await apiService.getMetricsCollectionStatus();
      set({ 
        collectionStatus: status,
        isCollecting: status.is_collecting || false
      });
    } catch (error: any) {
      console.error('Failed to fetch collection status:', error);
    }
  },

  startCollection: async (interval = 5) => {
    set({ isLoading: true, error: null });
    
    try {
      const result = await apiService.startMetricsCollection(interval);
      
      if (result.message) {
        set({ 
          isCollecting: true,
          isLoading: false 
        });
        
        // Refresh collection status
        get().fetchCollectionStatus();
        return true;
      }
      
      return false;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to start metrics collection';
      set({ error: errorMessage, isLoading: false });
      return false;
    }
  },

  stopCollection: async () => {
    set({ isLoading: true, error: null });
    
    try {
      const result = await apiService.stopMetricsCollection();
      
      if (result.message) {
        set({ 
          isCollecting: false,
          isLoading: false 
        });
        
        // Refresh collection status
        get().fetchCollectionStatus();
        return true;
      }
      
      return false;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to stop metrics collection';
      set({ error: errorMessage, isLoading: false });
      return false;
    }
  },

  updateMetricsFromWebSocket: (metricsData: SystemMetrics) => {
    const { metricsHistory } = get();
    
    // Update current metrics
    set({ currentMetrics: metricsData });
    
    // Add to history (keep last 100 entries)
    const newHistory = [...metricsHistory, metricsData].slice(-100);
    set({ metricsHistory: newHistory });
    
    // Update dashboard stats
    get().calculateDashboardStats();
  },

  calculateDashboardStats: () => {
    const { currentMetrics } = get();
    
    if (!currentMetrics) {
      return;
    }
    
    const stats: DashboardStats = {
      total_devices: 0, // This would come from device store
      online_devices: 0, // This would come from device store
      offline_devices: 0, // This would come from device store
      active_scans: 0, // This would come from device store
      active_alerts: 0, // This would come from alerts
      system_uptime: currentMetrics.system?.uptime_seconds || 0,
      cpu_usage: currentMetrics.cpu?.usage_percent || 0,
      memory_usage: currentMetrics.memory?.virtual?.percent || 0,
      network_throughput: {
        sent: currentMetrics.network?.total_io?.bytes_sent || 0,
        received: currentMetrics.network?.total_io?.bytes_recv || 0
      }
    };
    
    set({ dashboardStats: stats });
  },

  clearError: () => set({ error: null }),
  
  setLoading: (loading: boolean) => set({ isLoading: loading })
}));