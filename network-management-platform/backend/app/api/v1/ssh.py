"""
SSH management API endpoints
Remote command execution and file management
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
import logging

from app.services.ssh_manager import ssh_manager, SSHCredentials
from app.api.v1.auth import get_current_active_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class SSHConnectionRequest(BaseModel):
    """SSH connection request schema"""
    hostname: str
    port: int = 22
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_content: Optional[str] = None
    timeout: int = 30


class CommandRequest(BaseModel):
    """Command execution request schema"""
    command: str
    timeout: int = 30


class ScriptRequest(BaseModel):
    """Script execution request schema"""
    script_content: str
    script_name: str = "script.sh"


class BulkCommandRequest(BaseModel):
    """Bulk command execution request schema"""
    hosts: List[SSHConnectionRequest]
    command: str
    timeout: int = 30


@router.post("/test-connection")
async def test_ssh_connection(
    connection: SSHConnectionRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Test SSH connection to a host"""
    try:
        credentials = SSHCredentials(
            hostname=connection.hostname,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            private_key_path=connection.private_key_path,
            private_key_content=connection.private_key_content,
            timeout=connection.timeout
        )
        
        result = await ssh_manager.test_connection(credentials)
        return result
        
    except Exception as e:
        logger.error(f"SSH connection test failed: {e}")
        raise HTTPException(status_code=500, detail="SSH connection test failed")


@router.post("/execute")
async def execute_command(
    connection: SSHConnectionRequest,
    command: CommandRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute command on remote host"""
    try:
        credentials = SSHCredentials(
            hostname=connection.hostname,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            private_key_path=connection.private_key_path,
            private_key_content=connection.private_key_content,
            timeout=connection.timeout
        )
        
        stdout, stderr, exit_code = await ssh_manager.pool.execute_command(
            credentials, command.command, command.timeout
        )
        
        return {
            "hostname": connection.hostname,
            "command": command.command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "success": exit_code == 0
        }
        
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail="Command execution failed")


@router.post("/execute-bulk")
async def execute_bulk_commands(
    request: BulkCommandRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute command on multiple hosts"""
    try:
        targets = []
        for host_config in request.hosts:
            credentials = SSHCredentials(
                hostname=host_config.hostname,
                port=host_config.port,
                username=host_config.username,
                password=host_config.password,
                private_key_path=host_config.private_key_path,
                private_key_content=host_config.private_key_content,
                timeout=host_config.timeout
            )
            targets.append((credentials, request.command))
        
        results = await ssh_manager.pool.execute_commands_bulk(targets, request.timeout)
        
        return {
            "command": request.command,
            "results": {
                hostname: {
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "success": exit_code == 0
                }
                for hostname, (stdout, stderr, exit_code) in results.items()
            },
            "total_hosts": len(request.hosts),
            "successful": sum(1 for _, _, exit_code in results.values() if exit_code == 0)
        }
        
    except Exception as e:
        logger.error(f"Bulk command execution failed: {e}")
        raise HTTPException(status_code=500, detail="Bulk command execution failed")


@router.post("/execute-script")
async def execute_script(
    connection: SSHConnectionRequest,
    script: ScriptRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute script on remote host"""
    try:
        credentials = SSHCredentials(
            hostname=connection.hostname,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            private_key_path=connection.private_key_path,
            private_key_content=connection.private_key_content,
            timeout=connection.timeout
        )
        
        stdout, stderr, exit_code = await ssh_manager.run_script(
            credentials, script.script_content, script.script_name
        )
        
        return {
            "hostname": connection.hostname,
            "script_name": script.script_name,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "success": exit_code == 0
        }
        
    except Exception as e:
        logger.error(f"Script execution failed: {e}")
        raise HTTPException(status_code=500, detail="Script execution failed")


@router.get("/system-info")
async def get_system_info(
    hostname: str = Query(...),
    port: int = Query(22),
    username: str = Query(...),
    password: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Get system information from remote host"""
    try:
        credentials = SSHCredentials(
            hostname=hostname,
            port=port,
            username=username,
            password=password
        )
        
        system_info = await ssh_manager.pool.get_system_info(credentials)
        
        return {
            "hostname": hostname,
            "system_info": system_info
        }
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system info")


@router.post("/upload-file")
async def upload_file(
    hostname: str = Query(...),
    remote_path: str = Query(...),
    port: int = Query(22),
    username: str = Query(...),
    password: Optional[str] = Query(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload file to remote host"""
    try:
        import tempfile
        import os
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            credentials = SSHCredentials(
                hostname=hostname,
                port=port,
                username=username,
                password=password
            )
            
            success = await ssh_manager.pool.upload_file(
                credentials, tmp_file_path, remote_path
            )
            
            return {
                "hostname": hostname,
                "local_filename": file.filename,
                "remote_path": remote_path,
                "success": success,
                "file_size": len(content)
            }
            
        finally:
            # Cleanup temp file
            os.unlink(tmp_file_path)
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")


@router.post("/download-file")
async def download_file(
    hostname: str = Query(...),
    remote_path: str = Query(...),
    port: int = Query(22),
    username: str = Query(...),
    password: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Download file from remote host"""
    try:
        import tempfile
        import os
        from fastapi.responses import FileResponse
        
        credentials = SSHCredentials(
            hostname=hostname,
            port=port,
            username=username,
            password=password
        )
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
        
        try:
            success = await ssh_manager.pool.download_file(
                credentials, remote_path, tmp_file_path
            )
            
            if success:
                # Get filename from remote path
                filename = os.path.basename(remote_path)
                return FileResponse(
                    tmp_file_path,
                    filename=filename,
                    media_type='application/octet-stream'
                )
            else:
                raise HTTPException(status_code=404, detail="File not found or download failed")
                
        except HTTPException:
            os.unlink(tmp_file_path)
            raise
        
    except Exception as e:
        logger.error(f"File download failed: {e}")
        raise HTTPException(status_code=500, detail="File download failed")


@router.get("/pool-stats")
async def get_connection_pool_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get SSH connection pool statistics"""
    try:
        stats = ssh_manager.pool.get_connection_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pool statistics")


# Predefined common commands
COMMON_COMMANDS = {
    "uptime": "uptime",
    "disk_space": "df -h",
    "memory": "free -h",
    "processes": "ps aux --sort=-%cpu | head -10",
    "network_interfaces": "ip addr show",
    "system_info": "uname -a",
    "services": "systemctl list-units --type=service --state=running",
    "logs": "journalctl -n 50 --no-pager",
    "cpu_info": "lscpu",
    "mount_points": "mount | grep -v tmpfs"
}


@router.get("/commands/common")
async def get_common_commands():
    """Get list of common commands"""
    return {"commands": COMMON_COMMANDS}


@router.post("/commands/common/{command_name}")
async def execute_common_command(
    command_name: str,
    connection: SSHConnectionRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute a predefined common command"""
    if command_name not in COMMON_COMMANDS:
        raise HTTPException(status_code=404, detail="Command not found")
    
    try:
        credentials = SSHCredentials(
            hostname=connection.hostname,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            private_key_path=connection.private_key_path,
            private_key_content=connection.private_key_content,
            timeout=connection.timeout
        )
        
        command = COMMON_COMMANDS[command_name]
        stdout, stderr, exit_code = await ssh_manager.pool.execute_command(
            credentials, command, 30
        )
        
        return {
            "hostname": connection.hostname,
            "command_name": command_name,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "success": exit_code == 0
        }
        
    except Exception as e:
        logger.error(f"Common command execution failed: {e}")
        raise HTTPException(status_code=500, detail="Command execution failed")