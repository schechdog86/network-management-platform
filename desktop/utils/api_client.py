"""
API Client for backend integration
"""

import aiohttp
import asyncio
import json
import requests
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal, Slot
import websocket
import threading
from datetime import datetime

class APIClient(QObject):
    """API client for communicating with the backend"""
    
    # Signals for async operations
    connection_status_changed = Signal(bool)
    data_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, base_url: str, timeout: int = 30):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.auth_token = None
        self.session = None
        self.ws = None
        self.ws_thread = None
        
    def set_auth_token(self, token: str):
        """Set authentication token"""
        self.auth_token = token
        
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token"""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
        
    # Synchronous methods for immediate use
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login and get access token"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"username": username, "password": password},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_devices(self) -> Dict[str, Any]:
        """Get all network devices"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/devices",
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_network_status(self) -> Dict[str, Any]:
        """Get network status summary"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/network/status",
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def scan_network(self, subnet: str = None) -> Dict[str, Any]:
        """Trigger network scan"""
        try:
            params = {}
            if subnet:
                params["subnet"] = subnet
                
            response = requests.post(
                f"{self.base_url}/api/v1/network/scan",
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_metrics(self, device_id: str = None) -> Dict[str, Any]:
        """Get system metrics"""
        try:
            url = f"{self.base_url}/api/v1/metrics"
            if device_id:
                url = f"{url}/{device_id}"
                
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_backup_jobs(self) -> Dict[str, Any]:
        """Get backup jobs"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/backup/jobs",
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def create_backup_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new backup job"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/backup/jobs",
                headers=self._get_headers(),
                json=job_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_ai_chat_history(self) -> Dict[str, Any]:
        """Get AI chat history"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/ai/chat-history",
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def send_ai_command(self, command: str) -> Dict[str, Any]:
        """Send command to AI assistant"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/ai/process-command",
                headers=self._get_headers(),
                json={"command": command},
                timeout=self.timeout * 2  # Longer timeout for AI processing
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_predictive_maintenance(self) -> Dict[str, Any]:
        """Get predictive maintenance analysis"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/predictive-maintenance/analysis",
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    # WebSocket support for real-time updates
    def connect_websocket(self):
        """Connect to WebSocket for real-time updates"""
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws"
        
        if self.auth_token:
            ws_url = f"{ws_url}?token={self.auth_token}"
            
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.data_received.emit(data)
            except:
                pass
                
        def on_error(ws, error):
            self.error_occurred.emit(str(error))
            self.connection_status_changed.emit(False)
            
        def on_close(ws):
            self.connection_status_changed.emit(False)
            
        def on_open(ws):
            self.connection_status_changed.emit(True)
            
        def run_websocket():
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            self.ws.run_forever()
            
        self.ws_thread = threading.Thread(target=run_websocket)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
    def disconnect_websocket(self):
        """Disconnect WebSocket"""
        if self.ws:
            self.ws.close()
            
    def send_websocket_message(self, message: Dict[str, Any]):
        """Send message through WebSocket"""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(message))
            
class AsyncAPIClient(APIClient):
    """Async version of API client for better performance"""
    
    async def async_login(self, username: str, password: str) -> Dict[str, Any]:
        """Async login"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={"username": username, "password": password},
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.auth_token = data.get("access_token")
                        return {"success": True, "data": data}
                    else:
                        return {"success": False, "error": await response.text()}
            except Exception as e:
                return {"success": False, "error": str(e)}
                
    async def async_get_devices(self) -> Dict[str, Any]:
        """Async get devices"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/api/v1/devices",
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        return {"success": True, "data": await response.json()}
                    else:
                        return {"success": False, "error": await response.text()}
            except Exception as e:
                return {"success": False, "error": str(e)}
                
    async def async_get_metrics(self, device_id: str = None) -> Dict[str, Any]:
        """Async get metrics"""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}/api/v1/metrics"
                if device_id:
                    url = f"{url}/{device_id}"
                    
                async with session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        return {"success": True, "data": await response.json()}
                    else:
                        return {"success": False, "error": await response.text()}
            except Exception as e:
                return {"success": False, "error": str(e)}

# Global API client instance
api_client = None

def get_api_client(base_url: str = None) -> APIClient:
    """Get or create API client instance"""
    global api_client
    if not api_client:
        api_client = APIClient(base_url or "http://localhost:8000")
    return api_client