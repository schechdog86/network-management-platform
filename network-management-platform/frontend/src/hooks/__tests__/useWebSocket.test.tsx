import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket, useRealtimeUpdates, useWebSocketStatus } from '../useWebSocket';
import { wsService } from '@/services/websocket';
import { useDeviceStore } from '@/stores/deviceStore';
import { useMetricsStore } from '@/stores/metricsStore';
import { WebSocketMessage, WebSocketState } from '@/types';

// Mock the WebSocket service
jest.mock('@/services/websocket', () => ({
  wsService: {
    connect: jest.fn(),
    disconnect: jest.fn(),
    send: jest.fn(),
    subscribe: jest.fn(() => jest.fn()),
    subscribeToChannel: jest.fn(),
    unsubscribeFromChannel: jest.fn(),
    requestData: jest.fn(),
    onStateChange: jest.fn(() => jest.fn()),
    isConnected: jest.fn(() => false),
    getState: jest.fn(() => 'disconnected' as WebSocketState),
    getConnectionId: jest.fn(() => null),
  },
}));

// Mock the stores
jest.mock('@/stores/deviceStore', () => ({
  useDeviceStore: jest.fn(),
}));

jest.mock('@/stores/metricsStore', () => ({
  useMetricsStore: jest.fn(),
}));

describe('useWebSocket', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset mock implementations
    (wsService.isConnected as jest.Mock).mockReturnValue(false);
    (wsService.getState as jest.Mock).mockReturnValue('disconnected');
    (wsService.getConnectionId as jest.Mock).mockReturnValue(null);
  });

  describe('basic functionality', () => {
    it('should auto-connect when autoConnect is true', () => {
      renderHook(() => useWebSocket({ autoConnect: true }));
      
      expect(wsService.connect).toHaveBeenCalledTimes(1);
    });

    it('should not auto-connect when autoConnect is false', () => {
      renderHook(() => useWebSocket({ autoConnect: false }));
      
      expect(wsService.connect).not.toHaveBeenCalled();
    });

    it('should return connection methods', () => {
      const { result } = renderHook(() => useWebSocket());
      
      expect(result.current).toHaveProperty('connect');
      expect(result.current).toHaveProperty('disconnect');
      expect(result.current).toHaveProperty('send');
      expect(result.current).toHaveProperty('subscribeToChannel');
      expect(result.current).toHaveProperty('unsubscribeFromChannel');
      expect(result.current).toHaveProperty('requestData');
      expect(result.current).toHaveProperty('isConnected');
      expect(result.current).toHaveProperty('state');
      expect(result.current).toHaveProperty('connectionId');
    });

    it('should call wsService methods when hook methods are called', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));
      
      act(() => {
        result.current.connect();
      });
      expect(wsService.connect).toHaveBeenCalledTimes(1);
      
      act(() => {
        result.current.disconnect();
      });
      expect(wsService.disconnect).toHaveBeenCalledTimes(1);
      
      const testMessage = { type: 'test', data: 'hello' };
      act(() => {
        result.current.send(testMessage);
      });
      expect(wsService.send).toHaveBeenCalledWith(testMessage);
      
      act(() => {
        result.current.subscribeToChannel('test-channel');
      });
      expect(wsService.subscribeToChannel).toHaveBeenCalledWith('test-channel');
      
      act(() => {
        result.current.unsubscribeFromChannel('test-channel');
      });
      expect(wsService.unsubscribeFromChannel).toHaveBeenCalledWith('test-channel');
      
      act(() => {
        result.current.requestData('test-data');
      });
      expect(wsService.requestData).toHaveBeenCalledWith('test-data');
    });
  });

  describe('state management', () => {
    it('should reflect connection state', () => {
      (wsService.isConnected as jest.Mock).mockReturnValue(true);
      (wsService.getState as jest.Mock).mockReturnValue('connected');
      (wsService.getConnectionId as jest.Mock).mockReturnValue('test-connection-123');
      
      const { result } = renderHook(() => useWebSocket());
      
      expect(result.current.isConnected).toBe(true);
      expect(result.current.state).toBe('connected');
      expect(result.current.connectionId).toBe('test-connection-123');
    });

    it('should subscribe to state changes', () => {
      // This test verifies that the hook properly subscribes to state changes
      // The actual callback testing is complex due to the ref pattern used in the hook
      
      const onStateChange = jest.fn();
      renderHook(() => useWebSocket({ onStateChange }));
      
      // Verify that wsService.onStateChange was called to set up the subscription
      expect(wsService.onStateChange).toHaveBeenCalled();
      
      // The hook uses refs internally which makes testing the actual callback
      // execution complex. The important thing is that the subscription is set up.
    });
  });

  describe('message handling', () => {
    it('should subscribe to messages', () => {
      let messageCallback: ((message: WebSocketMessage) => void) | null = null;
      (wsService.subscribe as jest.Mock).mockImplementation((channel, cb) => {
        if (channel === '*') {
          messageCallback = cb;
        }
        return jest.fn();
      });
      
      const onMessage = jest.fn();
      renderHook(() => useWebSocket({ onMessage }));
      
      expect(wsService.subscribe).toHaveBeenCalledWith('*', expect.any(Function));
      
      // Simulate message
      const testMessage: WebSocketMessage = {
        type: 'device_update',
        data: { type: 'test' },
        timestamp: new Date().toISOString(),
      };
      
      act(() => {
        messageCallback?.(testMessage);
      });
      
      expect(onMessage).toHaveBeenCalledWith(testMessage);
    });
  });

  describe('channel subscription', () => {
    it('should subscribe to channels when connected', () => {
      let stateCallback: ((state: WebSocketState) => void) | null = null;
      (wsService.onStateChange as jest.Mock).mockImplementation((cb) => {
        stateCallback = cb;
        return jest.fn();
      });
      
      const channels = ['channel1', 'channel2'];
      renderHook(() => useWebSocket({ autoConnect: true, channels }));
      
      // Simulate connection
      act(() => {
        stateCallback?.('connected');
      });
      
      expect(wsService.subscribeToChannel).toHaveBeenCalledWith('channel1');
      expect(wsService.subscribeToChannel).toHaveBeenCalledWith('channel2');
    });
  });

  describe('cleanup', () => {
    it('should unsubscribe on unmount', () => {
      const unsubscribeMock = jest.fn();
      (wsService.subscribe as jest.Mock).mockReturnValue(unsubscribeMock);
      (wsService.onStateChange as jest.Mock).mockReturnValue(unsubscribeMock);
      
      const { unmount } = renderHook(() => useWebSocket());
      
      unmount();
      
      expect(unsubscribeMock).toHaveBeenCalled();
    });
  });
});

describe('useRealtimeUpdates', () => {
  let updateDeviceFromWebSocket: jest.Mock;
  let updateMetricsFromWebSocket: jest.Mock;
  let messageCallback: ((message: WebSocketMessage) => void) | null = null;

  beforeEach(() => {
    jest.clearAllMocks();
    
    updateDeviceFromWebSocket = jest.fn();
    updateMetricsFromWebSocket = jest.fn();
    
    (useDeviceStore as unknown as jest.Mock).mockReturnValue(updateDeviceFromWebSocket);
    (useMetricsStore as unknown as jest.Mock).mockReturnValue(updateMetricsFromWebSocket);
    
    (wsService.subscribe as jest.Mock).mockImplementation((channel, cb) => {
      if (channel === '*') {
        messageCallback = cb;
      }
      return jest.fn();
    });
  });

  it('should auto-connect and subscribe to channels', () => {
    renderHook(() => useRealtimeUpdates());
    
    expect(wsService.connect).toHaveBeenCalled();
  });

  it('should handle device update messages', () => {
    renderHook(() => useRealtimeUpdates());
    
    const deviceData = { id: '1', name: 'Device 1', ip_address: '192.168.1.1' };
    const message: WebSocketMessage = {
      type: 'device_update',
      data: deviceData,
      timestamp: new Date().toISOString(),
    };
    
    act(() => {
      messageCallback?.(message);
    });
    
    expect(updateDeviceFromWebSocket).toHaveBeenCalledWith(deviceData);
  });

  it('should handle system metrics messages', () => {
    renderHook(() => useRealtimeUpdates());
    
    const metricsData = { cpu: 50, memory: 75 };
    const message: WebSocketMessage = {
      type: 'system_metrics',
      data: metricsData,
      timestamp: new Date().toISOString(),
    };
    
    act(() => {
      messageCallback?.(message);
    });
    
    expect(updateMetricsFromWebSocket).toHaveBeenCalledWith(metricsData);
  });

  it('should log unhandled message types', () => {
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();
    
    renderHook(() => useRealtimeUpdates());
    
    const message: WebSocketMessage = {
      type: 'unknown' as any,
      data: { test: 'data' },
      timestamp: new Date().toISOString(),
    };
    
    act(() => {
      messageCallback?.(message);
    });
    
    expect(consoleLogSpy).toHaveBeenCalledWith('Unhandled WebSocket message:', message);
    
    consoleLogSpy.mockRestore();
  });

  it('should handle messages without data gracefully', () => {
    renderHook(() => useRealtimeUpdates());
    
    const message: WebSocketMessage = {
      type: 'device_update',
      timestamp: new Date().toISOString(),
    };
    
    act(() => {
      messageCallback?.(message);
    });
    
    expect(updateDeviceFromWebSocket).not.toHaveBeenCalled();
  });
});

describe('useWebSocketStatus', () => {
  let stateCallback: ((state: WebSocketState) => void) | null = null;

  beforeEach(() => {
    jest.clearAllMocks();
    
    (wsService.onStateChange as jest.Mock).mockImplementation((cb) => {
      stateCallback = cb;
      // Immediately call with current state
      cb('disconnected');
      return jest.fn();
    });
  });

  it('should provide connection status', () => {
    const { result } = renderHook(() => useWebSocketStatus());
    
    expect(result.current.state).toBe('disconnected');
    expect(result.current.isConnected).toBe(false);
    expect(result.current.isConnecting).toBe(false);
    expect(result.current.isDisconnected).toBe(true);
    expect(result.current.hasError).toBe(false);
  });

  it('should update status when state changes', async () => {
    const { result } = renderHook(() => useWebSocketStatus());
    
    act(() => {
      stateCallback?.('connecting');
    });
    
    expect(result.current.state).toBe('connecting');
    expect(result.current.isConnecting).toBe(true);
    expect(result.current.isConnected).toBe(false);
    
    act(() => {
      stateCallback?.('connected');
    });
    
    expect(result.current.state).toBe('connected');
    expect(result.current.isConnected).toBe(true);
    expect(result.current.isConnecting).toBe(false);
    
    act(() => {
      stateCallback?.('error');
    });
    
    expect(result.current.state).toBe('error');
    expect(result.current.hasError).toBe(true);
  });

  it('should unsubscribe on unmount', () => {
    const unsubscribeMock = jest.fn();
    (wsService.onStateChange as jest.Mock).mockReturnValue(unsubscribeMock);
    
    const { unmount } = renderHook(() => useWebSocketStatus());
    
    unmount();
    
    expect(unsubscribeMock).toHaveBeenCalled();
  });
});