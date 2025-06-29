"""
WebSocket API endpoints for real-time communication
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import HTMLResponse

from app.services.websocket_manager import websocket_manager
from app.core.auth import get_current_user_ws

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    Main WebSocket endpoint for real-time communication
    
    Query parameters:
    - client_id: Optional client identifier
    - token: Authentication token (required for production)
    """
    connection_id = None
    
    try:
        # For development, skip auth validation
        # In production, uncomment the following lines:
        # if not token:
        #     await websocket.close(code=4001, reason="Authentication required")
        #     return
        # 
        # user = await get_current_user_ws(token)
        # if not user:
        #     await websocket.close(code=4001, reason="Invalid token")
        #     return
        
        # Connect client
        connection_id = await websocket_manager.connection_manager.connect(
            websocket, client_id
        )
        
        # Handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Process client message
                await websocket_manager.handle_client_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client {connection_id} disconnected normally")
                break
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from client {connection_id}")
                await websocket_manager.connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "error",
                        "error": "Invalid JSON format",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                )
            except Exception as e:
                logger.error(f"Error processing message from {connection_id}: {e}")
                await websocket_manager.connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "error", 
                        "error": "Failed to process message",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                )
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        if connection_id:
            websocket_manager.connection_manager.disconnect(connection_id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics"""
    return websocket_manager.get_stats()


@router.get("/ws/test")
async def websocket_test_page():
    """Serve a simple WebSocket test page for development"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .log { background: #f5f5f5; padding: 10px; height: 400px; overflow-y: scroll; margin: 10px 0; }
            .controls { margin: 10px 0; }
            input, button, select { margin: 5px; padding: 5px; }
            .connected { color: green; }
            .disconnected { color: red; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Network Management Platform - WebSocket Test</h1>
            <div class="controls">
                <button id="connect">Connect</button>
                <button id="disconnect">Disconnect</button>
                <span id="status" class="disconnected">Disconnected</span>
            </div>
            
            <div class="controls">
                <select id="channelSelect">
                    <option value="devices">Devices</option>
                    <option value="metrics">System Metrics</option>
                    <option value="snmp">SNMP Data</option>
                    <option value="scans">Network Scans</option>
                    <option value="alerts">Alerts</option>
                </select>
                <button id="subscribe">Subscribe</button>
                <button id="unsubscribe">Unsubscribe</button>
            </div>
            
            <div class="controls">
                <select id="dataType">
                    <option value="device_list">Device List</option>
                    <option value="system_metrics">System Metrics</option>
                    <option value="connection_stats">Connection Stats</option>
                </select>
                <button id="requestData">Request Data</button>
            </div>
            
            <div id="log" class="log"></div>
            
            <div class="controls">
                <button id="clear">Clear Log</button>
            </div>
        </div>

        <script>
            let ws = null;
            const log = document.getElementById('log');
            const status = document.getElementById('status');
            
            function addLog(message, type = 'info') {
                const timestamp = new Date().toLocaleTimeString();
                const logEntry = document.createElement('div');
                logEntry.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
                if (type === 'error') logEntry.style.color = 'red';
                if (type === 'success') logEntry.style.color = 'green';
                log.appendChild(logEntry);
                log.scrollTop = log.scrollHeight;
            }
            
            function updateStatus(connected) {
                if (connected) {
                    status.textContent = 'Connected';
                    status.className = 'connected';
                } else {
                    status.textContent = 'Disconnected';
                    status.className = 'disconnected';
                }
            }
            
            document.getElementById('connect').onclick = function() {
                if (ws) return;
                
                const wsUrl = `ws://${window.location.host}/api/v1/websocket/ws`;
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    addLog('Connected to WebSocket', 'success');
                    updateStatus(true);
                };
                
                ws.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        addLog(`Received: ${JSON.stringify(data, null, 2)}`);
                    } catch (e) {
                        addLog(`Received: ${event.data}`);
                    }
                };
                
                ws.onclose = function() {
                    addLog('WebSocket connection closed', 'error');
                    updateStatus(false);
                    ws = null;
                };
                
                ws.onerror = function(error) {
                    addLog(`WebSocket error: ${error}`, 'error');
                };
            };
            
            document.getElementById('disconnect').onclick = function() {
                if (ws) {
                    ws.close();
                }
            };
            
            document.getElementById('subscribe').onclick = function() {
                if (!ws) return;
                const channel = document.getElementById('channelSelect').value;
                const message = {
                    type: 'subscribe',
                    channel: channel
                };
                ws.send(JSON.stringify(message));
                addLog(`Subscribing to channel: ${channel}`);
            };
            
            document.getElementById('unsubscribe').onclick = function() {
                if (!ws) return;
                const channel = document.getElementById('channelSelect').value;
                const message = {
                    type: 'unsubscribe',
                    channel: channel
                };
                ws.send(JSON.stringify(message));
                addLog(`Unsubscribing from channel: ${channel}`);
            };
            
            document.getElementById('requestData').onclick = function() {
                if (!ws) return;
                const dataType = document.getElementById('dataType').value;
                const message = {
                    type: 'request_data',
                    data_type: dataType
                };
                ws.send(JSON.stringify(message));
                addLog(`Requesting data: ${dataType}`);
            };
            
            document.getElementById('clear').onclick = function() {
                log.innerHTML = '';
            };
            
            // Add initial log entry
            addLog('WebSocket test page loaded. Click Connect to start.');
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/ws/broadcast/test")
async def broadcast_test_message(message: str = "Test message"):
    """Test endpoint to broadcast a message to all connected clients"""
    try:
        test_data = {
            "type": "test_message",
            "message": message,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        await websocket_manager.connection_manager.broadcast_to_all(test_data)
        
        return {
            "status": "success",
            "message": "Test message broadcasted",
            "connections": len(websocket_manager.connection_manager.active_connections)
        }
    except Exception as e:
        logger.error(f"Failed to broadcast test message: {e}")
        return {"status": "error", "message": str(e)}