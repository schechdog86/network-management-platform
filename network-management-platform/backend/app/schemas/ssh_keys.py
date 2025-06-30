"""
SSH Key Management Schemas
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re


class SSHKeyPairGenerate(BaseModel):
    """Request to generate SSH key pair"""
    node_id: str = Field(..., description="Node ID for the key pair")
    key_type: str = Field("ed25519", description="Key type (rsa, ed25519, ecdsa)")
    comment: Optional[str] = Field(None, description="Comment for the key")
    include_private: bool = Field(False, description="Include private key in response")
    
    @validator('key_type')
    def validate_key_type(cls, v):
        if v not in ['rsa', 'ed25519', 'ecdsa']:
            raise ValueError('Invalid key type. Must be rsa, ed25519, or ecdsa')
        return v


class SSHKeyPairResponse(BaseModel):
    """SSH key pair generation response"""
    node_id: str
    public_key: str
    private_key: Optional[str] = None
    fingerprint: str
    created_at: datetime


class SSHKeyCreate(BaseModel):
    """Add SSH public key"""
    node_id: str = Field(..., description="Node ID to add key to")
    public_key: str = Field(..., description="SSH public key")
    comment: Optional[str] = Field(None, description="Comment for the key")
    
    @validator('public_key')
    def validate_public_key(cls, v):
        # Basic validation - should start with ssh-rsa, ssh-ed25519, etc.
        if not re.match(r'^(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256) ', v):
            raise ValueError('Invalid SSH public key format')
        return v.strip()


class SSHKeyResponse(BaseModel):
    """SSH key response"""
    node_id: str
    public_key: str
    comment: Optional[str]
    fingerprint: str
    added_at: datetime


class SSHKeyInfo(BaseModel):
    """SSH key information"""
    type: str
    key: str
    comment: str
    fingerprint: str


class SSHKeyList(BaseModel):
    """List of SSH keys"""
    node_id: str
    keys: List[SSHKeyInfo]
    total: int


class SSHTestConnection(BaseModel):
    """Test SSH connection request"""
    hostname: str = Field(..., description="Hostname or IP to connect to")
    port: int = Field(22, description="SSH port")
    username: Optional[str] = Field(None, description="Username for SSH")
    node_id: Optional[str] = Field(None, description="Node ID to use for connection")


class SSHConnectionResult(BaseModel):
    """SSH connection test result"""
    hostname: str
    port: int
    username: str
    status: str
    error: Optional[str] = None
    server_version: Optional[str] = None


class SSHRemoteCommand(BaseModel):
    """Execute remote command via SSH"""
    hostname: str = Field(..., description="Hostname or IP")
    command: str = Field(..., description="Command to execute")
    username: Optional[str] = Field(None, description="SSH username")
    port: int = Field(22, description="SSH port")
    timeout: int = Field(30, ge=1, le=300, description="Command timeout in seconds")
    node_id: Optional[str] = Field(None, description="Node ID to use for connection")


class SSHCommandResult(BaseModel):
    """SSH command execution result"""
    hostname: str
    command: str
    exit_status: int
    stdout: str
    stderr: str
    error: Optional[str] = None


class SSHHostKey(BaseModel):
    """SSH host key scan request"""
    hostname: str = Field(..., description="Hostname or IP")
    port: int = Field(22, description="SSH port")
    add_to_known_hosts: bool = Field(False, description="Add to known hosts")
    node_id: Optional[str] = Field(None, description="Node ID if adding to known hosts")


class SSHHostKeyResponse(BaseModel):
    """SSH host key scan response"""
    hostname: str
    port: int
    host_key: str
    fingerprint: str


class SSHConfig(BaseModel):
    """SSH configuration entry"""
    host: str = Field(..., description="Host pattern")
    hostname: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    identity_file: Optional[str] = None
    strict_host_key_checking: Optional[str] = None
    user_known_hosts_file: Optional[str] = None
    additional_options: Optional[Dict[str, Any]] = None