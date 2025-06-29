// Custom hook for WebSocket management

import { useEffect, useCallback, useRef, useState } from 'react';
import { WebSocketMessage, WebSocketState } from '@/types';
import { wsService, WebSocketSubscriptionCallback } from '@/services/websocket';
import { useDeviceStore } from '@/stores/deviceStore';
import { useMetricsStore } from '@/stores/metricsStore';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  channels?: string[];
  onMessage?: (message: WebSocketMessage) => void;
  onStateChange?: (state: WebSocketState) => void;
}

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
  const {
    autoConnect = true,
    channels = [],
    onMessage,
    onStateChange
  } = options;
  
  const onMessageRef = useRef(onMessage);
  const onStateChangeRef = useRef(onStateChange);
  const channelsRef = useRef(channels);
  
  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);
  
  useEffect(() => {
    onStateChangeRef.current = onStateChange;
  }, [onStateChange]);
  
  useEffect(() => {
    channelsRef.current = channels;
  }, [channels]);

  // Subscribe to state changes
  useEffect(() => {
    const unsubscribe = wsService.onStateChange((state) => {
      onStateChangeRef.current?.(state);
    });
    
    return unsubscribe;
  }, []);

  // Subscribe to messages
  useEffect(() => {
    const unsubscribe = wsService.subscribe('*', (message) => {
      onMessageRef.current?.(message);
    });
    
    return unsubscribe;
  }, []);

  // Auto-connect and channel subscription
  useEffect(() => {
    if (autoConnect) {
      wsService.connect();
      
      // Subscribe to channels when connected
      const unsubscribeState = wsService.onStateChange((state) => {
        if (state === 'connected') {
          channelsRef.current.forEach(channel => {
            wsService.subscribeToChannel(channel);
          });
        }
      });
      
      return () => {
        unsubscribeState();
      };
    }
  }, [autoConnect]);

  const connect = useCallback(() => {
    wsService.connect();
  }, []);

  const disconnect = useCallback(() => {
    wsService.disconnect();
  }, []);

  const send = useCallback((message: any) => {
    wsService.send(message);
  }, []);

  const subscribeToChannel = useCallback((channel: string) => {
    wsService.subscribeToChannel(channel);
  }, []);

  const unsubscribeFromChannel = useCallback((channel: string) => {
    wsService.unsubscribeFromChannel(channel);
  }, []);

  const requestData = useCallback((dataType: string) => {
    wsService.requestData(dataType);
  }, []);

  return {
    connect,
    disconnect,
    send,
    subscribeToChannel,
    unsubscribeFromChannel,
    requestData,
    isConnected: wsService.isConnected(),
    state: wsService.getState(),
    connectionId: wsService.getConnectionId()
  };
};

// Hook for automatic real-time updates
export const useRealtimeUpdates = () => {
  const updateDeviceFromWebSocket = useDeviceStore(state => state.updateDeviceFromWebSocket);
  const updateMetricsFromWebSocket = useMetricsStore(state => state.updateMetricsFromWebSocket);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'device_update':
        if (message.data) {
          updateDeviceFromWebSocket(message.data);
        }
        break;
        
      case 'system_metrics':
        if (message.data) {
          updateMetricsFromWebSocket(message.data);
        }
        break;
        
      case 'snmp_data':
        // Handle SNMP data updates
        console.log('SNMP data received:', message);
        break;
        
      case 'alert':
        // Handle alerts
        console.log('Alert received:', message);
        break;
        
      default:
        console.log('Unhandled WebSocket message:', message);
    }
  }, [updateDeviceFromWebSocket, updateMetricsFromWebSocket]);

  useWebSocket({
    autoConnect: true,
    channels: ['devices', 'metrics', 'snmp', 'alerts'],
    onMessage: handleMessage
  });
};

// Hook for WebSocket connection status
export const useWebSocketStatus = () => {
  const [state, setState] = useState<WebSocketState>('disconnected');
  
  useEffect(() => {
    const unsubscribe = wsService.onStateChange(setState);
    return unsubscribe;
  }, []);
  
  return {
    state,
    isConnected: state === 'connected',
    isConnecting: state === 'connecting',
    isDisconnected: state === 'disconnected',
    hasError: state === 'error'
  };
};