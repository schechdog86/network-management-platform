"""
SSH Key Management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import asyncio
import json

from app.database import get_db
from app.auth import get_current_user
from app.models import User
from app.services.ssh_key_manager import SSHKeyManager
from app.services.websocket_manager import WebSocketManager
from app.schemas.ssh_keys import (
    SSHKeyCreate,
    SSHKeyResponse,
    SSHKeyList,
    SSHTestConnection,
    SSHConnectionResult,
    SSHRemoteCommand,
    SSHCommandResult,
    SSHKeyPairGenerate,
    SSHKeyPairResponse,
    SSHHostKey,
    SSHHostKeyResponse,
)

router = APIRouter()
ssh_manager = SSHKeyManager()
ws_manager = WebSocketManager()


@router.post("/generate", response_model=SSHKeyPairResponse)
async def generate_ssh_key_pair(
    request: SSHKeyPairGenerate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a new SSH key pair"""
    try:
        # Generate key pair
        private_key, public_key = await ssh_manager.generate_key_pair(
            key_type=request.key_type,
            comment=request.comment or f"{current_user.username}@network-platform",
            node_id=request.node_id
        )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "ssh_key_generated",
            "node_id": request.node_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return SSHKeyPairResponse(
            node_id=request.node_id,
            public_key=public_key,
            private_key=private_key if request.include_private else None,
            fingerprint=ssh_manager.get_key_fingerprint(public_key),
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SSH key: {str(e)}"
        )


@router.get("/list/{node_id}", response_model=SSHKeyList)
async def list_ssh_keys(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List SSH keys for a specific node"""
    try:
        keys = await ssh_manager.list_keys(node_id)
        
        return SSHKeyList(
            node_id=node_id,
            keys=keys,
            total=len(keys)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list SSH keys: {str(e)}"
        )


@router.post("/add", response_model=SSHKeyResponse)
async def add_ssh_key(
    request: SSHKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add an SSH public key to authorized_keys"""
    try:
        # Validate the public key format
        if not ssh_manager.validate_public_key(request.public_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SSH public key format"
            )
        
        # Add the key
        success = await ssh_manager.add_authorized_key(
            node_id=request.node_id,
            public_key=request.public_key,
            comment=request.comment
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Key already exists in authorized_keys"
            )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "ssh_key_added",
            "node_id": request.node_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return SSHKeyResponse(
            node_id=request.node_id,
            public_key=request.public_key,
            comment=request.comment,
            fingerprint=ssh_manager.get_key_fingerprint(request.public_key),
            added_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add SSH key: {str(e)}"
        )


@router.delete("/remove/{node_id}")
async def remove_ssh_key(
    node_id: str,
    fingerprint: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove an SSH key from authorized_keys"""
    try:
        success = await ssh_manager.remove_authorized_key(
            node_id=node_id,
            fingerprint=fingerprint
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Key not found in authorized_keys"
            )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "ssh_key_removed",
            "node_id": node_id,
            "fingerprint": fingerprint,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": "SSH key removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove SSH key: {str(e)}"
        )


@router.post("/test-connection", response_model=SSHConnectionResult)
async def test_ssh_connection(
    request: SSHTestConnection,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test SSH connection to a remote host"""
    try:
        result = await ssh_manager.test_connection(
            hostname=request.hostname,
            port=request.port,
            username=request.username,
            node_id=request.node_id
        )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "ssh_connection_test",
            "hostname": request.hostname,
            "status": result["status"],
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return SSHConnectionResult(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test SSH connection: {str(e)}"
        )


@router.post("/execute-command", response_model=SSHCommandResult)
async def execute_remote_command(
    request: SSHRemoteCommand,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a command on a remote host via SSH"""
    try:
        # Validate command (basic security check)
        if any(dangerous in request.command for dangerous in ['rm -rf /', 'dd if=', ':(){:|:&};:']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Command contains potentially dangerous operations"
            )
        
        result = await ssh_manager.execute_remote_command(
            hostname=request.hostname,
            command=request.command,
            username=request.username,
            port=request.port,
            timeout=request.timeout,
            node_id=request.node_id
        )
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "ssh_command_executed",
            "hostname": request.hostname,
            "command": request.command[:50] + "..." if len(request.command) > 50 else request.command,
            "exit_status": result["exit_status"],
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return SSHCommandResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute remote command: {str(e)}"
        )


@router.post("/scan-host-key", response_model=SSHHostKeyResponse)
async def scan_host_key(
    request: SSHHostKey,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Scan and retrieve SSH host key"""
    try:
        host_key = await ssh_manager.scan_host_key(
            hostname=request.hostname,
            port=request.port
        )
        
        if not host_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to retrieve host key"
            )
        
        # Optionally add to known hosts
        if request.add_to_known_hosts and request.node_id:
            await ssh_manager.add_known_host(
                node_id=request.node_id,
                hostname=request.hostname,
                host_key=host_key
            )
        
        return SSHHostKeyResponse(
            hostname=request.hostname,
            port=request.port,
            host_key=host_key,
            fingerprint=ssh_manager.get_host_key_fingerprint(host_key)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan host key: {str(e)}"
        )


@router.get("/config/{node_id}")
async def get_ssh_config(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get SSH configuration for a node"""
    try:
        config = await ssh_manager.get_ssh_config(node_id)
        
        return {
            "node_id": node_id,
            "config": config
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SSH config: {str(e)}"
        )


@router.put("/config/{node_id}")
async def update_ssh_config(
    node_id: str,
    config: List[dict],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update SSH configuration for a node"""
    try:
        await ssh_manager.update_ssh_config(node_id, config)
        
        # Send WebSocket notification
        await ws_manager.broadcast(json.dumps({
            "type": "ssh_config_updated",
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": "SSH configuration updated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update SSH config: {str(e)}"
        )