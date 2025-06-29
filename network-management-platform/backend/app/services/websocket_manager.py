"""
Enhanced WebSocket manager for real-time monitoring and updates
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum
import weakref

from app.core.redis_client import cache_manager
from app.models.device import Device

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types"""
    DEVICE_UPDATE = "device_update"
    SYSTEM_METRICS = "system_metrics"
    NETWORK_SCAN = "network_scan"
    ALERT = "alert"
    BULK_ACTION = "bulk_action"
    SNMP_DATA = "snmp_data"
    CONNECTION_STATUS = "connection_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ConnectionManager:
    """Manages WebSocket connections with advanced features"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # connection_id -> set of channels
        self.channels: Dict[str, Set[str]] = {}  # channel -> set of connection_ids
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Accept WebSocket connection and return connection ID"""
        await websocket.accept()
        
        connection_id = client_id or str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow().isoformat(),
            "user_agent": websocket.headers.get("user-agent", ""),
            "ip_address": websocket.client.host if websocket.client else "unknown"
        }
        self.subscriptions[connection_id] = set()
        
        # Start heartbeat monitoring
        self.heartbeat_tasks[connection_id] = asyncio.create_task(
            self._heartbeat_monitor(connection_id)
        )
        
        await self.send_personal_message(connection_id, {
            "type": MessageType.CONNECTION_STATUS.value,
            "status": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"WebSocket client connected: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            # Cancel heartbeat task
            if connection_id in self.heartbeat_tasks:
                self.heartbeat_tasks[connection_id].cancel()
                del self.heartbeat_tasks[connection_id]
            
            # Remove from all channels
            if connection_id in self.subscriptions:
                for channel in self.subscriptions[connection_id]:
                    if channel in self.channels:
                        self.channels[channel].discard(connection_id)
                del self.subscriptions[connection_id]
            
            # Remove connection
            del self.active_connections[connection_id]
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]
            
            logger.info(f"WebSocket client disconnected: {connection_id}")
    
    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast message to all connections in a channel"""
        if channel in self.channels:
            disconnected = []
            for connection_id in self.channels[channel].copy():
                try:
                    await self.send_personal_message(connection_id, message)
                except:
                    disconnected.append(connection_id)
            
            # Clean up disconnected clients
            for connection_id in disconnected:
                self.disconnect(connection_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(connection_id, message)
            except:
                disconnected.append(connection_id)
        
        # Clean up disconnected clients
        for connection_id in disconnected:
            self.disconnect(connection_id)
    
    async def subscribe_to_channel(self, connection_id: str, channel: str):
        """Subscribe connection to a channel"""
        if connection_id in self.active_connections:
            self.subscriptions[connection_id].add(channel)
            if channel not in self.channels:
                self.channels[channel] = set()
            self.channels[channel].add(connection_id)
            
            await self.send_personal_message(connection_id, {
                "type": "subscription_confirmed",
                "channel": channel,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Client {connection_id} subscribed to channel: {channel}")
    
    async def unsubscribe_from_channel(self, connection_id: str, channel: str):
        """Unsubscribe connection from a channel"""
        if connection_id in self.subscriptions:
            self.subscriptions[connection_id].discard(channel)
        
        if channel in self.channels:
            self.channels[channel].discard(connection_id)
        
        await self.send_personal_message(connection_id, {
            "type": "subscription_cancelled",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Client {connection_id} unsubscribed from channel: {channel}")
    
    async def _heartbeat_monitor(self, connection_id: str):
        """Monitor connection health with heartbeat"""
        try:
            while connection_id in self.active_connections:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
                if connection_id in self.active_connections:
                    await self.send_personal_message(connection_id, {
                        "type": MessageType.HEARTBEAT.value,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Update last heartbeat
                    if connection_id in self.connection_metadata:
                        self.connection_metadata[connection_id]["last_heartbeat"] = \
                            datetime.utcnow().isoformat()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat monitor error for {connection_id}: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "channels": {channel: len(connections) for channel, connections in self.channels.items()},
            "connections": {
                conn_id: {
                    "metadata": self.connection_metadata.get(conn_id, {}),
                    "subscriptions": list(self.subscriptions.get(conn_id, set()))
                }
                for conn_id in self.active_connections.keys()
            }
        }


class WebSocketManager:
    """Enhanced WebSocket manager with real-time monitoring capabilities"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.data_cache: Dict[str, Any] = {}
        
    async def handle_client_message(self, connection_id: str, message: Dict[str, Any]):
        """Handle incoming client messages"""
        try:
            message_type = message.get("type")
            
            if message_type == "subscribe":
                channel = message.get("channel")
                if channel:
                    await self.connection_manager.subscribe_to_channel(connection_id, channel)
            
            elif message_type == "unsubscribe":
                channel = message.get("channel")
                if channel:
                    await self.connection_manager.unsubscribe_from_channel(connection_id, channel)
            
            elif message_type == "request_data":
                data_type = message.get("data_type")
                await self._handle_data_request(connection_id, data_type)
            
            elif message_type == "heartbeat_response":
                # Update heartbeat timestamp
                if connection_id in self.connection_manager.connection_metadata:
                    self.connection_manager.connection_metadata[connection_id]["last_heartbeat"] = \
                        datetime.utcnow().isoformat()
            
            else:
                await self.connection_manager.send_personal_message(connection_id, {
                    "type": MessageType.ERROR.value,
                    "error": f"Unknown message type: {message_type}",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling client message from {connection_id}: {e}")
            await self.connection_manager.send_personal_message(connection_id, {
                "type": MessageType.ERROR.value,
                "error": "Failed to process message",
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def _handle_data_request(self, connection_id: str, data_type: str):
        """Handle client data requests"""
        try:
            if data_type == "device_list":
                # Send current device list from cache
                devices = await cache_manager.get("active_devices") or []
                await self.connection_manager.send_personal_message(connection_id, {
                    "type": MessageType.DEVICE_UPDATE.value,
                    "data": devices,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif data_type == "system_metrics":
                # Send current system metrics
                metrics = await cache_manager.get("system_metrics") or {}
                await self.connection_manager.send_personal_message(connection_id, {
                    "type": MessageType.SYSTEM_METRICS.value,
                    "data": metrics,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif data_type == "connection_stats":
                # Send connection statistics
                stats = self.connection_manager.get_connection_stats()
                await self.connection_manager.send_personal_message(connection_id, {
                    "type": "connection_stats",
                    "data": stats,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling data request {data_type} from {connection_id}: {e}")
    
    async def broadcast_device_update(self, device_data: Dict[str, Any]):
        """Broadcast device status update"""
        message = {
            "type": MessageType.DEVICE_UPDATE.value,
            "data": device_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_channel("devices", message)
        
        # Cache the update
        await cache_manager.set(f"device_{device_data.get('id')}", device_data, ttl=300)
    
    async def broadcast_system_metrics(self, metrics_data: Dict[str, Any]):
        """Broadcast system metrics update"""
        message = {
            "type": MessageType.SYSTEM_METRICS.value,
            "data": metrics_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_channel("metrics", message)
        
        # Cache the metrics
        await cache_manager.set("system_metrics", metrics_data, ttl=60)
    
    async def broadcast_snmp_data(self, device_id: str, snmp_data: Dict[str, Any]):
        """Broadcast SNMP monitoring data"""
        message = {
            "type": MessageType.SNMP_DATA.value,
            "device_id": device_id,
            "data": snmp_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_channel("snmp", message)
        await self.connection_manager.broadcast_to_channel(f"device_{device_id}", message)
    
    async def broadcast_alert(self, alert_data: Dict[str, Any]):
        """Broadcast system alert"""
        message = {
            "type": MessageType.ALERT.value,
            "data": alert_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_all(message)
        
        # Cache critical alerts
        if alert_data.get("severity") in ["critical", "high"]:
            alerts = await cache_manager.get("active_alerts") or []
            alerts.append(alert_data)
            await cache_manager.set("active_alerts", alerts, ttl=3600)
    
    async def broadcast_scan_progress(self, scan_id: str, progress_data: Dict[str, Any]):
        """Broadcast network scan progress"""
        message = {
            "type": MessageType.NETWORK_SCAN.value,
            "scan_id": scan_id,
            "data": progress_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_channel("scans", message)
        await self.connection_manager.broadcast_to_channel(f"scan_{scan_id}", message)
    
    async def broadcast_bulk_action_progress(self, action_id: str, progress_data: Dict[str, Any]):
        """Broadcast bulk action progress"""
        message = {
            "type": MessageType.BULK_ACTION.value,
            "action_id": action_id,
            "data": progress_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_channel("bulk_actions", message)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        return {
            "connections": self.connection_manager.get_connection_stats(),
            "monitoring_tasks": len(self.monitoring_tasks),
            "cache_entries": len(self.data_cache)
        }


# Global WebSocket manager instance
websocket_manager = WebSocketManager()