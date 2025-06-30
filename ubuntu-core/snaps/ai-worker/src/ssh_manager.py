#!/usr/bin/env python3
"""
SSH management for AI worker nodes.
Manages SSH keys, authorized access, and secure connections.
"""

import os
import subprocess
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import paramiko
import asyncssh

logger = logging.getLogger(__name__)


class SSHManager:
    """Manages SSH configuration and connections for worker nodes"""
    
    def __init__(self):
        # SSH directories
        self.ssh_dir = Path.home() / '.ssh'
        self.ssh_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Key files
        self.private_key_path = self.ssh_dir / 'id_ed25519'
        self.public_key_path = self.ssh_dir / 'id_ed25519.pub'
        self.authorized_keys_path = self.ssh_dir / 'authorized_keys'
        self.known_hosts_path = self.ssh_dir / 'known_hosts'
        
        # SSH config
        self.ssh_config_path = self.ssh_dir / 'config'
        
        # Ensure proper permissions
        self._ensure_permissions()
        
    def _ensure_permissions(self):
        """Ensure proper permissions on SSH files"""
        # Set directory permissions
        self.ssh_dir.chmod(0o700)
        
        # Set file permissions if they exist
        if self.private_key_path.exists():
            self.private_key_path.chmod(0o600)
        if self.authorized_keys_path.exists():
            self.authorized_keys_path.chmod(0o600)
        if self.ssh_config_path.exists():
            self.ssh_config_path.chmod(0o644)
            
    async def generate_ssh_key(self, key_type: str = 'ed25519', 
                              comment: Optional[str] = None) -> Tuple[str, str]:
        """Generate SSH key pair"""
        try:
            if comment is None:
                comment = f"ai-worker@{os.uname().nodename}"
                
            # Generate key using ssh-keygen
            cmd = [
                'ssh-keygen',
                '-t', key_type,
                '-f', str(self.private_key_path),
                '-C', comment,
                '-N', ''  # No passphrase
            ]
            
            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"ssh-keygen failed: {stderr.decode()}")
                
            # Read generated keys
            private_key = self.private_key_path.read_text()
            public_key = self.public_key_path.read_text().strip()
            
            # Set proper permissions
            self._ensure_permissions()
            
            logger.info(f"Generated SSH {key_type} key pair")
            
            return private_key, public_key
            
        except Exception as e:
            logger.error(f"Error generating SSH key: {e}")
            raise
            
    def get_public_key(self) -> Optional[str]:
        """Get the public SSH key"""
        if self.public_key_path.exists():
            return self.public_key_path.read_text().strip()
        return None
        
    def add_authorized_key(self, public_key: str, comment: Optional[str] = None):
        """Add a public key to authorized_keys"""
        try:
            # Ensure the key ends with a newline
            if not public_key.endswith('\n'):
                public_key += '\n'
                
            # Add comment if provided
            if comment and not public_key.strip().endswith(comment):
                public_key = public_key.strip() + f" {comment}\n"
                
            # Read existing keys
            existing_keys = set()
            if self.authorized_keys_path.exists():
                existing_keys = set(self.authorized_keys_path.read_text().splitlines())
                
            # Check if key already exists
            key_line = public_key.strip()
            if key_line not in existing_keys:
                # Append the key
                with open(self.authorized_keys_path, 'a') as f:
                    f.write(public_key)
                    
                # Set proper permissions
                self.authorized_keys_path.chmod(0o600)
                
                logger.info(f"Added authorized key: {key_line[:50]}...")
                return True
            else:
                logger.info("Key already in authorized_keys")
                return False
                
        except Exception as e:
            logger.error(f"Error adding authorized key: {e}")
            raise
            
    def remove_authorized_key(self, public_key: str) -> bool:
        """Remove a public key from authorized_keys"""
        try:
            if not self.authorized_keys_path.exists():
                return False
                
            # Read existing keys
            lines = self.authorized_keys_path.read_text().splitlines()
            
            # Filter out the key
            key_line = public_key.strip()
            new_lines = [line for line in lines if line.strip() != key_line]
            
            if len(new_lines) < len(lines):
                # Write back the filtered keys
                self.authorized_keys_path.write_text('\n'.join(new_lines) + '\n')
                logger.info(f"Removed authorized key: {key_line[:50]}...")
                return True
            else:
                logger.info("Key not found in authorized_keys")
                return False
                
        except Exception as e:
            logger.error(f"Error removing authorized key: {e}")
            raise
            
    def list_authorized_keys(self) -> List[Dict[str, str]]:
        """List all authorized keys"""
        keys = []
        
        if self.authorized_keys_path.exists():
            for line in self.authorized_keys_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        key_info = {
                            'type': parts[0],
                            'key': parts[1],
                            'comment': ' '.join(parts[2:]) if len(parts) > 2 else ''
                        }
                        keys.append(key_info)
                        
        return keys
        
    def add_known_host(self, hostname: str, host_key: str):
        """Add a host to known_hosts"""
        try:
            # Format the known_hosts entry
            entry = f"{hostname} {host_key}\n"
            
            # Check if already exists
            existing_entries = set()
            if self.known_hosts_path.exists():
                existing_entries = set(self.known_hosts_path.read_text().splitlines())
                
            if entry.strip() not in existing_entries:
                with open(self.known_hosts_path, 'a') as f:
                    f.write(entry)
                logger.info(f"Added known host: {hostname}")
                
        except Exception as e:
            logger.error(f"Error adding known host: {e}")
            raise
            
    async def scan_host_key(self, hostname: str, port: int = 22) -> Optional[str]:
        """Scan and retrieve host key"""
        try:
            cmd = ['ssh-keyscan', '-p', str(port), hostname]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Parse the output to get the host key
                for line in stdout.decode().splitlines():
                    if line and not line.startswith('#'):
                        return line
                        
            logger.warning(f"Failed to scan host key for {hostname}: {stderr.decode()}")
            return None
            
        except Exception as e:
            logger.error(f"Error scanning host key: {e}")
            return None
            
    def create_ssh_config(self, configs: List[Dict[str, Any]]):
        """Create or update SSH config file"""
        try:
            config_lines = []
            
            for config in configs:
                host = config.get('host', '*')
                config_lines.append(f"Host {host}")
                
                # Add config options
                for key, value in config.items():
                    if key != 'host':
                        # Convert key from snake_case to PascalCase
                        ssh_key = ''.join(word.capitalize() for word in key.split('_'))
                        config_lines.append(f"  {ssh_key} {value}")
                        
                config_lines.append("")  # Empty line between hosts
                
            # Write config
            self.ssh_config_path.write_text('\n'.join(config_lines))
            self.ssh_config_path.chmod(0o644)
            
            logger.info("Updated SSH config")
            
        except Exception as e:
            logger.error(f"Error creating SSH config: {e}")
            raise
            
    async def test_ssh_connection(self, hostname: str, username: str = None, 
                                 port: int = 22) -> Dict[str, Any]:
        """Test SSH connection to a host"""
        result = {
            'hostname': hostname,
            'port': port,
            'username': username or os.getlogin(),
            'status': 'unknown',
            'error': None,
            'server_version': None
        }
        
        try:
            # Try to connect using asyncssh
            async with asyncssh.connect(
                hostname,
                port=port,
                username=result['username'],
                known_hosts=str(self.known_hosts_path) if self.known_hosts_path.exists() else None,
                client_keys=[str(self.private_key_path)] if self.private_key_path.exists() else None
            ) as conn:
                # Get server information
                result['server_version'] = conn.get_extra_info('server_version')
                result['status'] = 'connected'
                
                # Try to run a simple command
                try:
                    result_cmd = await conn.run('echo "SSH test successful"')
                    if result_cmd.exit_status == 0:
                        result['status'] = 'authenticated'
                except Exception:
                    result['status'] = 'connected_no_auth'
                    
        except asyncssh.DisconnectError as e:
            result['status'] = 'disconnected'
            result['error'] = str(e)
        except asyncssh.PermissionDenied:
            result['status'] = 'permission_denied'
            result['error'] = 'Authentication failed'
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            
        return result
        
    async def execute_remote_command(self, hostname: str, command: str, 
                                   username: str = None, port: int = 22,
                                   timeout: int = 30) -> Dict[str, Any]:
        """Execute a command on a remote host via SSH"""
        result = {
            'hostname': hostname,
            'command': command,
            'exit_status': -1,
            'stdout': '',
            'stderr': '',
            'error': None
        }
        
        try:
            async with asyncssh.connect(
                hostname,
                port=port,
                username=username or os.getlogin(),
                known_hosts=str(self.known_hosts_path) if self.known_hosts_path.exists() else None,
                client_keys=[str(self.private_key_path)] if self.private_key_path.exists() else None
            ) as conn:
                # Execute command with timeout
                result_cmd = await asyncio.wait_for(
                    conn.run(command),
                    timeout=timeout
                )
                
                result['exit_status'] = result_cmd.exit_status
                result['stdout'] = result_cmd.stdout
                result['stderr'] = result_cmd.stderr
                
        except asyncio.TimeoutError:
            result['error'] = f'Command timed out after {timeout} seconds'
        except Exception as e:
            result['error'] = str(e)
            
        return result
        
    async def copy_file_to_remote(self, local_path: str, remote_path: str,
                                 hostname: str, username: str = None, 
                                 port: int = 22) -> Dict[str, Any]:
        """Copy a file to a remote host via SCP"""
        result = {
            'local_path': local_path,
            'remote_path': remote_path,
            'hostname': hostname,
            'status': 'unknown',
            'error': None
        }
        
        try:
            async with asyncssh.connect(
                hostname,
                port=port,
                username=username or os.getlogin(),
                known_hosts=str(self.known_hosts_path) if self.known_hosts_path.exists() else None,
                client_keys=[str(self.private_key_path)] if self.private_key_path.exists() else None
            ) as conn:
                # Copy file
                await asyncssh.scp(local_path, (conn, remote_path))
                result['status'] = 'success'
                
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            
        return result


async def main():
    """Test SSH manager functionality"""
    logging.basicConfig(level=logging.INFO)
    
    manager = SSHManager()
    
    # Generate SSH key if it doesn't exist
    if not manager.get_public_key():
        print("Generating SSH key...")
        private_key, public_key = await manager.generate_ssh_key()
        print(f"Public key: {public_key[:50]}...")
    else:
        print(f"Public key: {manager.get_public_key()[:50]}...")
        
    # List authorized keys
    print("\nAuthorized keys:")
    for key in manager.list_authorized_keys():
        print(f"- {key['type']} {key['key'][:30]}... {key['comment']}")
        
    # Test SSH connection (example)
    # result = await manager.test_ssh_connection('localhost')
    # print(f"\nSSH test result: {result}")


if __name__ == "__main__":
    asyncio.run(main())