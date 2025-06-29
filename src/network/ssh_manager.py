import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import paramiko
import socket
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@dataclass
class SSHConnection:
    hostname: str
    username: str
    port: int = 22
    client: Optional[paramiko.SSHClient] = None
    last_used: Optional[datetime] = None
    is_connected: bool = False

class SSHConnectionPool:
    """Async SSH connection pool with automatic cleanup and reconnection."""
    
    def __init__(self, max_connections: int = 50, connection_timeout: int = 30):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.connections: Dict[str, SSHConnection] = {}
        self._lock = asyncio.Lock()
        
    def _create_connection_key(self, hostname: str, username: str, port: int = 22) -> str:
        """Create unique key for connection."""
        return f"{username}@{hostname}:{port}"
    
    async def get_connection(self, hostname: str, username: str, 
                           password: str = None, key_filename: str = None, 
                           port: int = 22) -> paramiko.SSHClient:
        """Get or create SSH connection from pool."""
        key = self._create_connection_key(hostname, username, port)
        
        async with self._lock:
            # Check if connection exists and is valid
            if key in self.connections:
                conn = self.connections[key]
                if conn.is_connected and self._test_connection(conn.client):
                    conn.last_used = datetime.now()
                    return conn.client
                else:
                    # Remove invalid connection
                    await self._close_connection(key)
            
            # Create new connection
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                # Connect with provided credentials
                if key_filename:
                    client.connect(
                        hostname, port=port, username=username,
                        key_filename=key_filename, timeout=self.connection_timeout
                    )
                elif password:
                    client.connect(
                        hostname, port=port, username=username,
                        password=password, timeout=self.connection_timeout
                    )
                else:
                    # Try agent authentication
                    client.connect(
                        hostname, port=port, username=username,
                        timeout=self.connection_timeout
                    )
                
                # Store connection
                self.connections[key] = SSHConnection(
                    hostname=hostname,
                    username=username,
                    port=port,
                    client=client,
                    last_used=datetime.now(),
                    is_connected=True
                )
                
                logger.info(f"Created SSH connection to {hostname}")
                return client
                
            except Exception as e:
                logger.error(f"Failed to create SSH connection to {hostname}: {e}")
                client.close()
                raise
    
    def _test_connection(self, client: paramiko.SSHClient) -> bool:
        """Test if SSH connection is still alive."""
        try:
            transport = client.get_transport()
            if transport and transport.is_active():
                # Send a simple command to test
                transport.send_ignore()
                return True
        except Exception:
            pass
        return False
    
    async def execute_command(self, hostname: str, username: str, command: str,
                             password: str = None, key_filename: str = None,
                             port: int = 22, timeout: int = 30) -> Dict[str, Any]:
        """Execute command via SSH and return result."""
        try:
            client = await self.get_connection(
                hostname, username, password, key_filename, port
            )
            
            # Execute command
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            
            # Get results
            exit_status = stdout.channel.recv_exit_status()
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            
            return {
                'hostname': hostname,
                'command': command,
                'exit_status': exit_status,
                'stdout': stdout_data,
                'stderr': stderr_data,
                'success': exit_status == 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Command execution failed on {hostname}: {e}")
            return {
                'hostname': hostname,
                'command': command,
                'exit_status': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _close_connection(self, key: str):
        """Close and remove connection."""
        if key in self.connections:
            conn = self.connections[key]
            if conn.client:
                conn.client.close()
            del self.connections[key]
            logger.info(f"Closed SSH connection: {key}")
    
    async def cleanup_idle_connections(self, max_idle_minutes: int = 30):
        """Clean up idle connections."""
        current_time = datetime.now()
        keys_to_remove = []
        
        async with self._lock:
            for key, conn in self.connections.items():
                if conn.last_used:
                    idle_time = (current_time - conn.last_used).total_seconds() / 60
                    if idle_time > max_idle_minutes:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                await self._close_connection(key)
    
    async def close_all_connections(self):
        """Close all connections in pool."""
        async with self._lock:
            for key in list(self.connections.keys()):
                await self._close_connection(key)

# Global connection pool instance
ssh_pool = SSHConnectionPool()

@asynccontextmanager
async def get_ssh_connection(hostname: str, username: str, 
                           password: str = None, key_filename: str = None,
                           port: int = 22):
    """Context manager for SSH connections."""
    client = None
    try:
        client = await ssh_pool.get_connection(
            hostname, username, password, key_filename, port
        )
        yield client
    finally:
        # Connection stays in pool for reuse
        pass

async def execute_ssh_command(hostname: str, username: str, command: str,
                             **kwargs) -> Dict[str, Any]:
    """Convenience function to execute SSH command."""
    return await ssh_pool.execute_command(
        hostname, username, command, **kwargs
    )

# Example usage
async def main():
    """Example usage of SSH connection pool."""
    # Execute command on remote server
    result = await execute_ssh_command(
        hostname="192.168.1.100",
        username="admin",
        command="uptime",
        key_filename="/home/user/.ssh/id_rsa"
    )
    
    print(f"Command result: {result}")
    
    # Clean up connections
    await ssh_pool.cleanup_idle_connections(max_idle_minutes=5)

if __name__ == "__main__":
    asyncio.run(main())
