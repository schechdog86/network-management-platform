// WebSocket service for real-time communication

import { WebSocketMessage, WebSocketState } from '@/types';

export type WebSocketSubscriptionCallback = (message: WebSocketMessage) => void;
export type WebSocketStateCallback = (state: WebSocketState) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000; // Start with 1 second
  private subscriptions = new Map<string, Set<WebSocketSubscriptionCallback>>();
  private stateCallbacks = new Set<WebSocketStateCallback>();
  private currentState: WebSocketState = 'disconnected';
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private connectionId: string | null = null;

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${protocol}//${window.location.host}/api/v1/websocket/ws`;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    this.setState('connecting');
    console.log('Connecting to WebSocket:', this.url);

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.setState('error');
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    console.log('Disconnecting WebSocket');
    this.clearTimers();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.setState('disconnected');
    this.reconnectAttempts = 0;
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.setState('connected');
      this.reconnectAttempts = 0;
      this.reconnectInterval = 1000;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error, event.data);
      }
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      this.clearTimers();
      this.setState('disconnected');
      
      // Only attempt reconnect if it wasn't a normal closure
      if (event.code !== 1000) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.setState('error');
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    console.log('Received WebSocket message:', message);

    // Handle special message types
    switch (message.type) {
      case 'connection_status':
        if (message.data?.connection_id) {
          this.connectionId = message.data.connection_id;
          console.log('Connection ID received:', this.connectionId);
        }
        break;
      case 'heartbeat':
        this.sendHeartbeatResponse();
        break;
    }

    // Notify subscribers
    const callbacks = this.subscriptions.get(message.type);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(message);
        } catch (error) {
          console.error('Error in WebSocket callback:', error);
        }
      });
    }

    // Notify wildcard subscribers
    const wildcardCallbacks = this.subscriptions.get('*');
    if (wildcardCallbacks) {
      wildcardCallbacks.forEach(callback => {
        try {
          callback(message);
        } catch (error) {
          console.error('Error in wildcard WebSocket callback:', error);
        }
      });
    }
  }

  private sendHeartbeatResponse(): void {
    this.send({
      type: 'heartbeat_response',
      timestamp: new Date().toISOString()
    });
  }

  private startHeartbeat(): void {
    this.clearTimers();
    // Respond to server heartbeats every 30 seconds
    this.heartbeatTimer = setInterval(() => {
      if (this.currentState === 'connected') {
        // Server sends heartbeat, we don't need to send one
        // Just verify connection is still alive
        if (this.ws?.readyState !== WebSocket.OPEN) {
          console.log('WebSocket connection lost, attempting reconnect');
          this.scheduleReconnect();
        }
      }
    }, 35000); // Check slightly after expected heartbeat interval
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnect attempts reached');
      this.setState('error');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 30000);
    
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
    
    this.reconnectTimer = setTimeout(() => {
      console.log(`Reconnect attempt ${this.reconnectAttempts}`);
      this.connect();
    }, delay);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private setState(state: WebSocketState): void {
    if (this.currentState !== state) {
      console.log(`WebSocket state changed: ${this.currentState} -> ${state}`);
      this.currentState = state;
      this.stateCallbacks.forEach(callback => {
        try {
          callback(state);
        } catch (error) {
          console.error('Error in state callback:', error);
        }
      });
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
      }
    } else {
      console.warn('WebSocket not connected, cannot send message:', message);
    }
  }

  subscribe(messageType: string, callback: WebSocketSubscriptionCallback): () => void {
    if (!this.subscriptions.has(messageType)) {
      this.subscriptions.set(messageType, new Set());
    }
    
    this.subscriptions.get(messageType)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      const callbacks = this.subscriptions.get(messageType);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.subscriptions.delete(messageType);
        }
      }
    };
  }

  subscribeToChannel(channel: string): void {
    this.send({
      type: 'subscribe',
      channel: channel
    });
  }

  unsubscribeFromChannel(channel: string): void {
    this.send({
      type: 'unsubscribe',
      channel: channel
    });
  }

  requestData(dataType: string): void {
    this.send({
      type: 'request_data',
      data_type: dataType
    });
  }

  onStateChange(callback: WebSocketStateCallback): () => void {
    this.stateCallbacks.add(callback);
    
    // Immediately call with current state
    callback(this.currentState);
    
    // Return unsubscribe function
    return () => {
      this.stateCallbacks.delete(callback);
    };
  }

  getState(): WebSocketState {
    return this.currentState;
  }

  getConnectionId(): string | null {
    return this.connectionId;
  }

  isConnected(): boolean {
    return this.currentState === 'connected';
  }
}

// Create and export singleton instance
export const wsService = new WebSocketService();
export default wsService;