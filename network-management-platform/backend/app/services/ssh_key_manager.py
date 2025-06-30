"""
SSH Key Manager Service
Manages SSH keys across worker nodes
"""

import os
import asyncio
import logging
import hashlib
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import asyncssh
import subprocess

from app.core.config import settings

logger = logging.getLogger(__name__)


class SSHKeyManager:
    """Manages SSH keys for network nodes"""
    
    def __init__(self):
        # Base directory for SSH keys
        self.ssh_base_dir = Path(settings.DATA_DIR) / "ssh_keys"
        self.ssh_base_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_node_ssh_dir(self, node_id: str) -> Path:
        """Get SSH directory for a specific node"""
        node_dir = self.ssh_base_dir / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        return node_dir
        
    async def generate_key_pair(self, key_type: str = "ed25519", 
                               comment: Optional[str] = None,
                               node_id: str = "default") -> Tuple[str, str]:
        """Generate SSH key pair for a node"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            private_key_path = node_dir / f"id_{key_type}"
            public_key_path = node_dir / f"id_{key_type}.pub"
            
            # Generate key using ssh-keygen
            cmd = [
                'ssh-keygen',
                '-t', key_type,
                '-f', str(private_key_path),
                '-C', comment or f"network-platform@{node_id}",
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
            private_key = private_key_path.read_text()
            public_key = public_key_path.read_text().strip()
            
            # Set proper permissions
            private_key_path.chmod(0o600)
            
            logger.info(f"Generated SSH {key_type} key pair for node {node_id}")
            
            return private_key, public_key
            
        except Exception as e:
            logger.error(f"Error generating SSH key: {e}")
            raise
            
    def validate_public_key(self, public_key: str) -> bool:
        """Validate SSH public key format"""
        try:
            # Basic format check
            parts = public_key.strip().split()
            if len(parts) < 2:
                return False
                
            # Check key type
            if parts[0] not in ['ssh-rsa', 'ssh-ed25519', 'ecdsa-sha2-nistp256', 
                               'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521']:
                return False
                
            # Try to decode the key data
            try:
                base64.b64decode(parts[1])
            except:
                return False
                
            return True
            
        except Exception:
            return False
            
    def get_key_fingerprint(self, public_key: str) -> str:
        """Get fingerprint of SSH public key"""
        try:
            # Parse the key
            parts = public_key.strip().split()
            if len(parts) < 2:
                raise ValueError("Invalid public key format")
                
            # Decode key data
            key_data = base64.b64decode(parts[1])
            
            # Calculate SHA256 fingerprint
            digest = hashlib.sha256(key_data).digest()
            fingerprint = base64.b64encode(digest).decode('utf-8').rstrip('=')
            
            return f"SHA256:{fingerprint}"
            
        except Exception as e:
            logger.error(f"Error calculating fingerprint: {e}")
            return "invalid"
            
    def get_host_key_fingerprint(self, host_key: str) -> str:
        """Get fingerprint of SSH host key"""
        try:
            # Host key format: hostname key_type key_data
            parts = host_key.strip().split()
            if len(parts) < 3:
                raise ValueError("Invalid host key format")
                
            # Use the key data (third part)
            key_data = base64.b64decode(parts[2])
            
            # Calculate SHA256 fingerprint
            digest = hashlib.sha256(key_data).digest()
            fingerprint = base64.b64encode(digest).decode('utf-8').rstrip('=')
            
            return f"SHA256:{fingerprint}"
            
        except Exception as e:
            logger.error(f"Error calculating host key fingerprint: {e}")
            return "invalid"
            
    async def list_keys(self, node_id: str) -> List[Dict[str, str]]:
        """List SSH keys for a node"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            authorized_keys_path = node_dir / "authorized_keys"
            
            keys = []
            
            if authorized_keys_path.exists():
                for line in authorized_keys_path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2:
                            key_info = {
                                'type': parts[0],
                                'key': parts[1],
                                'comment': ' '.join(parts[2:]) if len(parts) > 2 else '',
                                'fingerprint': self.get_key_fingerprint(line)
                            }
                            keys.append(key_info)
                            
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys: {e}")
            return []
            
    async def add_authorized_key(self, node_id: str, public_key: str, 
                                comment: Optional[str] = None) -> bool:
        """Add public key to authorized_keys"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            authorized_keys_path = node_dir / "authorized_keys"
            
            # Ensure the key ends with a newline
            if not public_key.endswith('\n'):
                public_key += '\n'
                
            # Add comment if provided and not already in key
            if comment and not public_key.strip().endswith(comment):
                public_key = public_key.strip() + f" {comment}\n"
                
            # Read existing keys
            existing_keys = set()
            if authorized_keys_path.exists():
                existing_keys = set(authorized_keys_path.read_text().splitlines())
                
            # Check if key already exists
            key_line = public_key.strip()
            if key_line not in existing_keys:
                # Append the key
                with open(authorized_keys_path, 'a') as f:
                    f.write(public_key)
                    
                # Set proper permissions
                authorized_keys_path.chmod(0o600)
                
                logger.info(f"Added authorized key for node {node_id}")
                return True
            else:
                logger.info(f"Key already exists for node {node_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding authorized key: {e}")
            raise
            
    async def remove_authorized_key(self, node_id: str, fingerprint: str) -> bool:
        """Remove a public key from authorized_keys by fingerprint"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            authorized_keys_path = node_dir / "authorized_keys"
            
            if not authorized_keys_path.exists():
                return False
                
            # Read existing keys
            lines = authorized_keys_path.read_text().splitlines()
            
            # Filter out the key with matching fingerprint
            new_lines = []
            removed = False
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    if self.get_key_fingerprint(line) == fingerprint:
                        removed = True
                        continue
                new_lines.append(line)
                
            if removed:
                # Write back the filtered keys
                authorized_keys_path.write_text('\n'.join(new_lines) + '\n')
                logger.info(f"Removed authorized key for node {node_id}")
                return True
            else:
                logger.info(f"Key not found for node {node_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing authorized key: {e}")
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
            
    async def add_known_host(self, node_id: str, hostname: str, host_key: str):
        """Add host to known_hosts"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            known_hosts_path = node_dir / "known_hosts"
            
            # Format the known_hosts entry
            entry = f"{hostname} {host_key}\n"
            
            # Check if already exists
            existing_entries = set()
            if known_hosts_path.exists():
                existing_entries = set(known_hosts_path.read_text().splitlines())
                
            if entry.strip() not in existing_entries:
                with open(known_hosts_path, 'a') as f:
                    f.write(entry)
                logger.info(f"Added known host {hostname} for node {node_id}")
                
        except Exception as e:
            logger.error(f"Error adding known host: {e}")
            raise
            
    async def get_ssh_config(self, node_id: str) -> List[Dict[str, Any]]:
        """Get SSH configuration for a node"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            config_path = node_dir / "config"
            
            if not config_path.exists():
                return []
                
            # Parse SSH config
            configs = []
            current_host = None
            
            for line in config_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                if line.startswith('Host '):
                    if current_host:
                        configs.append(current_host)
                    current_host = {'host': line.split()[1]}
                elif current_host and ' ' in line:
                    key, value = line.split(None, 1)
                    # Convert SSH config key to snake_case
                    key = key.lower().replace('hostname', 'hostname')
                    current_host[key] = value
                    
            if current_host:
                configs.append(current_host)
                
            return configs
            
        except Exception as e:
            logger.error(f"Error getting SSH config: {e}")
            return []
            
    async def update_ssh_config(self, node_id: str, configs: List[Dict[str, Any]]):
        """Update SSH configuration for a node"""
        try:
            node_dir = self._get_node_ssh_dir(node_id)
            config_path = node_dir / "config"
            
            config_lines = []
            
            for config in configs:
                host = config.get('host', '*')
                config_lines.append(f"Host {host}")
                
                # Add config options
                for key, value in config.items():
                    if key != 'host':
                        # Convert key to SSH config format
                        ssh_key = ''.join(word.capitalize() for word in key.split('_'))
                        config_lines.append(f"  {ssh_key} {value}")
                        
                config_lines.append("")  # Empty line between hosts
                
            # Write config
            config_path.write_text('\n'.join(config_lines))
            config_path.chmod(0o644)
            
            logger.info(f"Updated SSH config for node {node_id}")
            
        except Exception as e:
            logger.error(f"Error updating SSH config: {e}")
            raise
            
    async def test_connection(self, hostname: str, port: int = 22,
                             username: Optional[str] = None,
                             node_id: Optional[str] = None) -> Dict[str, Any]:
        """Test SSH connection"""
        result = {
            'hostname': hostname,
            'port': port,
            'username': username or os.getlogin(),
            'status': 'unknown',
            'error': None,
            'server_version': None
        }
        
        try:
            # Get SSH keys for the node
            private_key_path = None
            known_hosts_path = None
            
            if node_id:
                node_dir = self._get_node_ssh_dir(node_id)
                # Look for private keys
                for key_type in ['ed25519', 'rsa', 'ecdsa']:
                    key_path = node_dir / f"id_{key_type}"
                    if key_path.exists():
                        private_key_path = str(key_path)
                        break
                        
                # Known hosts
                kh_path = node_dir / "known_hosts"
                if kh_path.exists():
                    known_hosts_path = str(kh_path)
                    
            # Try to connect
            async with asyncssh.connect(
                hostname,
                port=port,
                username=result['username'],
                known_hosts=known_hosts_path,
                client_keys=[private_key_path] if private_key_path else None
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
                                   username: Optional[str] = None, port: int = 22,
                                   timeout: int = 30, node_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute command on remote host"""
        result = {
            'hostname': hostname,
            'command': command,
            'exit_status': -1,
            'stdout': '',
            'stderr': '',
            'error': None
        }
        
        try:
            # Get SSH keys for the node
            private_key_path = None
            known_hosts_path = None
            
            if node_id:
                node_dir = self._get_node_ssh_dir(node_id)
                # Look for private keys
                for key_type in ['ed25519', 'rsa', 'ecdsa']:
                    key_path = node_dir / f"id_{key_type}"
                    if key_path.exists():
                        private_key_path = str(key_path)
                        break
                        
                # Known hosts
                kh_path = node_dir / "known_hosts"
                if kh_path.exists():
                    known_hosts_path = str(kh_path)
                    
            async with asyncssh.connect(
                hostname,
                port=port,
                username=username or os.getlogin(),
                known_hosts=known_hosts_path,
                client_keys=[private_key_path] if private_key_path else None
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