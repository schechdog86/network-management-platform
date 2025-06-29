"""
SSH connection management service with connection pooling
"""

import asyncio
import logging
import paramiko
import socket
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import concurrent.futures
import threading
import time
import io

logger = logging.getLogger(__name__)


@dataclass
class SSHCredentials:
    """SSH connection credentials"""
    hostname: str
    port: int = 22
    username: str = "root"
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_content: Optional[str] = None
    timeout: int = 30


@dataclass
class SSHConnection:
    """SSH connection wrapper"""
    client: paramiko.SSHClient
    credentials: SSHCredentials
    created_at: datetime
    last_used: datetime
    is_connected: bool = True
    connection_id: str = field(default_factory=lambda: str(time.time()))


class SSHConnectionPool:
    """SSH connection pool for managing multiple connections"""
    
    def __init__(self, max_connections: int = 50, connection_timeout: int = 300):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout  # seconds
        self.connections: Dict[str, SSHConnection] = {}
        self.lock = threading.Lock()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        
        # Start cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background task to cleanup old connections"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(60)  # Check every minute
                    await self._cleanup_old_connections()
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
        
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def _cleanup_old_connections(self):
        """Remove old and unused connections"""
        with self.lock:
            current_time = datetime.now()
            to_remove = []
            
            for key, conn in self.connections.items():
                if (current_time - conn.last_used).seconds > self.connection_timeout:
                    to_remove.append(key)
                    try:
                        conn.client.close()
                    except:
                        pass
            
            for key in to_remove:
                del self.connections[key]
                logger.info(f"Removed expired SSH connection: {key}")
    
    def _get_connection_key(self, credentials: SSHCredentials) -> str:
        """Generate unique key for connection"""
        return f"{credentials.hostname}:{credentials.port}:{credentials.username}"
    
    async def get_connection(self, credentials: SSHCredentials) -> Optional[SSHConnection]:
        """Get or create SSH connection"""
        connection_key = self._get_connection_key(credentials)
        
        with self.lock:
            # Check if connection exists and is still valid
            if connection_key in self.connections:
                conn = self.connections[connection_key]
                if self._is_connection_alive(conn):
                    conn.last_used = datetime.now()
                    return conn
                else:
                    # Remove dead connection
                    try:
                        conn.client.close()
                    except:
                        pass
                    del self.connections[connection_key]
        
        # Create new connection
        try:
            loop = asyncio.get_event_loop()
            ssh_client = await loop.run_in_executor(
                self.executor, self._create_ssh_client, credentials
            )
            
            if ssh_client:
                conn = SSHConnection(
                    client=ssh_client,
                    credentials=credentials,
                    created_at=datetime.now(),
                    last_used=datetime.now()
                )
                
                with self.lock:
                    # Check connection limit
                    if len(self.connections) >= self.max_connections:
                        # Remove oldest connection
                        oldest_key = min(
                            self.connections.keys(),
                            key=lambda k: self.connections[k].last_used
                        )
                        old_conn = self.connections.pop(oldest_key)
                        try:
                            old_conn.client.close()
                        except:
                            pass
                    
                    self.connections[connection_key] = conn
                
                logger.info(f"Created new SSH connection: {connection_key}")
                return conn
            
        except Exception as e:
            logger.error(f"Failed to create SSH connection to {credentials.hostname}: {e}")
        
        return None
    
    def _create_ssh_client(self, credentials: SSHCredentials) -> Optional[paramiko.SSHClient]:
        """Create SSH client in thread"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Prepare authentication
            connect_kwargs = {
                'hostname': credentials.hostname,
                'port': credentials.port,
                'username': credentials.username,
                'timeout': credentials.timeout,
                'banner_timeout': 30,
                'auth_timeout': 30
            }
            
            # Add authentication method
            if credentials.private_key_content:
                # Use private key from content
                key_file = io.StringIO(credentials.private_key_content)
                private_key = paramiko.RSAKey.from_private_key(key_file)
                connect_kwargs['pkey'] = private_key
            elif credentials.private_key_path:
                # Use private key from file
                private_key = paramiko.RSAKey.from_private_key_file(credentials.private_key_path)
                connect_kwargs['pkey'] = private_key
            elif credentials.password:
                # Use password authentication
                connect_kwargs['password'] = credentials.password
            else:
                logger.error("No authentication method provided")
                return None
            
            # Connect
            client.connect(**connect_kwargs)
            
            # Test connection
            transport = client.get_transport()
            if transport and transport.is_active():
                return client
            else:
                client.close()
                return None
                
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return None
    
    def _is_connection_alive(self, conn: SSHConnection) -> bool:
        """Check if SSH connection is still alive"""
        try:
            transport = conn.client.get_transport()
            return transport and transport.is_active()
        except:
            return False
    
    async def execute_command(
        self, 
        credentials: SSHCredentials, 
        command: str, 
        timeout: int = 30
    ) -> Tuple[str, str, int]:
        """Execute command on remote host"""
        connection = await self.get_connection(credentials)
        if not connection:
            raise Exception(f"Failed to establish SSH connection to {credentials.hostname}")
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, self._execute_command_sync, connection, command, timeout
            )
        except Exception as e:
            logger.error(f"Command execution failed on {credentials.hostname}: {e}")
            raise
    
    def _execute_command_sync(
        self, 
        connection: SSHConnection, 
        command: str, 
        timeout: int
    ) -> Tuple[str, str, int]:
        """Execute command synchronously"""
        try:
            stdin, stdout, stderr = connection.client.exec_command(
                command, timeout=timeout
            )
            
            # Get exit code
            exit_code = stdout.channel.recv_exit_status()
            
            # Read output
            stdout_data = stdout.read().decode('utf-8', errors='replace')
            stderr_data = stderr.read().decode('utf-8', errors='replace')
            
            connection.last_used = datetime.now()
            
            return stdout_data, stderr_data, exit_code
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            raise
    
    async def execute_commands_bulk(
        self, 
        targets: List[Tuple[SSHCredentials, str]], 
        timeout: int = 30
    ) -> Dict[str, Tuple[str, str, int]]:
        """Execute commands on multiple hosts concurrently"""
        tasks = []
        
        for credentials, command in targets:
            task = asyncio.create_task(
                self.execute_command(credentials, command, timeout)
            )
            tasks.append((credentials.hostname, task))
        
        results = {}
        for hostname, task in tasks:
            try:
                stdout, stderr, exit_code = await task
                results[hostname] = (stdout, stderr, exit_code)
            except Exception as e:
                results[hostname] = ("", str(e), -1)
        
        return results
    
    async def upload_file(
        self, 
        credentials: SSHCredentials, 
        local_path: str, 
        remote_path: str
    ) -> bool:
        """Upload file to remote host"""
        connection = await self.get_connection(credentials)
        if not connection:
            raise Exception(f"Failed to establish SSH connection to {credentials.hostname}")
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, self._upload_file_sync, connection, local_path, remote_path
            )
        except Exception as e:
            logger.error(f"File upload failed to {credentials.hostname}: {e}")
            raise
    
    def _upload_file_sync(
        self, 
        connection: SSHConnection, 
        local_path: str, 
        remote_path: str
    ) -> bool:
        """Upload file synchronously"""
        try:
            sftp = connection.client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            
            connection.last_used = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"SFTP upload error: {e}")
            return False
    
    async def download_file(
        self, 
        credentials: SSHCredentials, 
        remote_path: str, 
        local_path: str
    ) -> bool:
        """Download file from remote host"""
        connection = await self.get_connection(credentials)
        if not connection:
            raise Exception(f"Failed to establish SSH connection to {credentials.hostname}")
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, self._download_file_sync, connection, remote_path, local_path
            )
        except Exception as e:
            logger.error(f"File download failed from {credentials.hostname}: {e}")
            raise
    
    def _download_file_sync(
        self, 
        connection: SSHConnection, 
        remote_path: str, 
        local_path: str
    ) -> bool:
        """Download file synchronously"""
        try:
            sftp = connection.client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            
            connection.last_used = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"SFTP download error: {e}")
            return False
    
    async def get_system_info(self, credentials: SSHCredentials) -> Dict[str, Any]:
        """Get basic system information from remote host"""
        commands = {
            "hostname": "hostname",
            "uptime": "uptime",
            "kernel": "uname -r",
            "os_release": "cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null || echo 'Unknown'",
            "cpu_info": "lscpu | grep -E '(Model name|CPU\\(s\\)|Architecture)' || echo 'Unknown'",
            "memory": "free -h",
            "disk_usage": "df -h",
            "network_interfaces": "ip addr show || ifconfig",
            "processes": "ps aux --sort=-%cpu | head -10"
        }
        
        results = {}
        for key, command in commands.items():
            try:
                stdout, stderr, exit_code = await self.execute_command(
                    credentials, command, timeout=15
                )
                results[key] = {
                    "output": stdout.strip(),
                    "error": stderr.strip() if stderr else None,
                    "exit_code": exit_code
                }
            except Exception as e:
                results[key] = {
                    "output": "",
                    "error": str(e),
                    "exit_code": -1
                }
        
        return results
    
    async def close_all_connections(self):
        """Close all SSH connections"""
        with self.lock:
            for conn in self.connections.values():
                try:
                    conn.client.close()
                except:
                    pass
            self.connections.clear()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        with self.lock:
            active_connections = sum(
                1 for conn in self.connections.values() 
                if self._is_connection_alive(conn)
            )
            
            return {
                "total_connections": len(self.connections),
                "active_connections": active_connections,
                "max_connections": self.max_connections,
                "connection_timeout": self.connection_timeout
            }


# Global SSH connection pool
ssh_pool = SSHConnectionPool()


class SSHManager:
    """High-level SSH management service"""
    
    def __init__(self, connection_pool: SSHConnectionPool = None):
        self.pool = connection_pool or ssh_pool
    
    async def test_connection(self, credentials: SSHCredentials) -> Dict[str, Any]:
        """Test SSH connection to host"""
        try:
            start_time = time.time()
            connection = await self.pool.get_connection(credentials)
            connect_time = time.time() - start_time
            
            if connection:
                # Test with simple command
                stdout, stderr, exit_code = await self.pool.execute_command(
                    credentials, "echo 'test'", timeout=5
                )
                
                return {
                    "success": True,
                    "connect_time": connect_time,
                    "test_output": stdout.strip(),
                    "hostname": credentials.hostname
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to establish connection",
                    "hostname": credentials.hostname
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "hostname": credentials.hostname
            }
    
    async def run_script(
        self, 
        credentials: SSHCredentials, 
        script_content: str, 
        script_name: str = "script.sh"
    ) -> Tuple[str, str, int]:
        """Upload and execute a script on remote host"""
        try:
            # Create temporary script file content
            remote_script_path = f"/tmp/{script_name}"
            
            # Upload script content
            # First create the script locally
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as tmp_file:
                tmp_file.write(script_content)
                tmp_file_path = tmp_file.name
            
            try:
                # Upload script
                await self.pool.upload_file(credentials, tmp_file_path, remote_script_path)
                
                # Make executable and run
                await self.pool.execute_command(
                    credentials, f"chmod +x {remote_script_path}", timeout=10
                )
                
                stdout, stderr, exit_code = await self.pool.execute_command(
                    credentials, remote_script_path, timeout=300
                )
                
                # Cleanup remote script
                await self.pool.execute_command(
                    credentials, f"rm -f {remote_script_path}", timeout=10
                )
                
                return stdout, stderr, exit_code
                
            finally:
                # Cleanup local temp file
                os.unlink(tmp_file_path)
                
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            raise


# Global SSH manager instance
ssh_manager = SSHManager()