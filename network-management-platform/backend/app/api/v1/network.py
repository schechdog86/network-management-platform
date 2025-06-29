"""
Network management API endpoints
Network topology, scanning, and monitoring
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import ray
import logging

from app.core.database import get_db
from app.core.ray_cluster import get_ray_manager
from app.models.network import Network, NetworkTopology
from app.schemas.network import (
    NetworkCreate, NetworkUpdate, NetworkResponse,
    TopologyResponse, ScanRequest, SubnetScanRequest
)
from app.services.network_discovery import network_discovery
from app.services.ssh_manager import ssh_manager, SSHCredentials

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[NetworkResponse])
async def get_networks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    network_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get list of managed networks"""
    try:
        network_service = NetworkService(db)
        networks = await network_service.get_networks(
            skip=skip,
            limit=limit,
            network_type=network_type
        )
        return networks
    except Exception as e:
        logger.error(f"Failed to get networks: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve networks")


@router.get("/{network_id}", response_model=NetworkResponse)
async def get_network(network_id: str, db: AsyncSession = Depends(get_db)):
    """Get specific network by ID"""
    try:
        network_service = NetworkService(db)
        network = await network_service.get_network(network_id)
        if not network:
            raise HTTPException(status_code=404, detail="Network not found")
        return network
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get network {network_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve network")


@router.post("/", response_model=NetworkResponse)
async def create_network(
    network: NetworkCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new network"""
    try:
        network_service = NetworkService(db)
        created_network = await network_service.create_network(network)
        return created_network
    except Exception as e:
        logger.error(f"Failed to create network: {e}")
        raise HTTPException(status_code=500, detail="Failed to create network")


@router.put("/{network_id}", response_model=NetworkResponse)
async def update_network(
    network_id: str,
    network_update: NetworkUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update network information"""
    try:
        network_service = NetworkService(db)
        updated_network = await network_service.update_network(network_id, network_update)
        if not updated_network:
            raise HTTPException(status_code=404, detail="Network not found")
        return updated_network
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update network {network_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update network")


@router.delete("/{network_id}")
async def delete_network(network_id: str, db: AsyncSession = Depends(get_db)):
    """Delete network"""
    try:
        network_service = NetworkService(db)
        success = await network_service.delete_network(network_id)
        if not success:
            raise HTTPException(status_code=404, detail="Network not found")
        return {"message": "Network deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete network {network_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete network")


@router.get("/topology/discovery")
async def get_network_topology(
    network_id: Optional[str] = Query(None),
    depth: int = Query(3, ge=1, le=10),
    ray_manager = Depends(get_ray_manager)
):
    """Discover and return network topology using GPU acceleration"""
    try:
        if not ray.is_initialized():
            raise HTTPException(status_code=503, detail="Ray cluster not available")
        
        scanner_service = NetworkScannerService(ray_manager)
        topology = await scanner_service.discover_network_topology(
            network_id=network_id,
            discovery_depth=depth
        )
        
        return topology
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to discover network topology: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover network topology")


@router.post("/scan/subnet")
async def scan_subnet(
    scan_request: SubnetScanRequest,
    background_tasks: BackgroundTasks,
    ray_manager = Depends(get_ray_manager)
):
    """Initiate subnet scan with GPU acceleration"""
    try:
        if not ray.is_initialized():
            raise HTTPException(status_code=503, detail="Ray cluster not available")
        
        scanner_service = NetworkScannerService(ray_manager)
        scan_id = await scanner_service.start_subnet_scan(scan_request)
        
        return {
            "scan_id": scan_id,
            "message": "Subnet scan initiated",
            "subnet": scan_request.subnet,
            "scan_type": scan_request.scan_type,
            "estimated_duration": "2-5 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start subnet scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate subnet scan")


@router.get("/scan/{scan_id}")
async def get_scan_results(
    scan_id: str,
    ray_manager = Depends(get_ray_manager)
):
    """Get network scan results"""
    try:
        scanner_service = NetworkScannerService(ray_manager)
        results = await scanner_service.get_scan_results(scan_id)
        if not results:
            raise HTTPException(status_code=404, detail="Scan not found")
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan results {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scan results")


@router.post("/discovery/subnet")
async def discover_subnet(
    network: str = Query(..., description="Network range (e.g., 192.168.1.0/24)"),
    scan_type: str = Query("ping", regex="^(ping|tcp|udp|comprehensive)$")
):
    """Discover devices on a network subnet"""
    try:
        result = await network_discovery.discover_network(network, scan_type)
        return result
    except Exception as e:
        logger.error(f"Failed to discover subnet {network}: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover subnet")


@router.post("/discovery/ping")
async def ping_host(host: str = Query(..., description="Hostname or IP address")):
    """Ping a single host"""
    try:
        result = await network_discovery.ping_host(host)
        return result
    except Exception as e:
        logger.error(f"Failed to ping {host}: {e}")
        raise HTTPException(status_code=500, detail="Failed to ping host")


@router.post("/discovery/port-scan")
async def scan_ports(
    host: str = Query(..., description="Hostname or IP address"),
    ports: str = Query("22,23,25,53,80,443", description="Comma-separated port list")
):
    """Scan ports on a host"""
    try:
        result = await network_discovery.port_scan(host, ports)
        return result
    except Exception as e:
        logger.error(f"Failed to scan ports on {host}: {e}")
        raise HTTPException(status_code=500, detail="Failed to scan ports")


@router.get("/interfaces")
async def get_network_interfaces():
    """Get local network interfaces"""
    try:
        interfaces = await network_discovery.get_network_interfaces()
        return {"interfaces": interfaces}
    except Exception as e:
        logger.error(f"Failed to get network interfaces: {e}")
        raise HTTPException(status_code=500, detail="Failed to get network interfaces")


@router.post("/traceroute")
async def traceroute_host(
    host: str = Query(..., description="Hostname or IP address"),
    max_hops: int = Query(30, ge=1, le=50)
):
    """Perform traceroute to host"""
    try:
        result = await network_discovery.traceroute(host, max_hops)
        return result
    except Exception as e:
        logger.error(f"Failed to traceroute {host}: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform traceroute")


@router.get("/monitor/bandwidth")
async def get_bandwidth_metrics(
    network_id: Optional[str] = Query(None),
    interface: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    db: AsyncSession = Depends(get_db)
):
    """Get network bandwidth metrics"""
    try:
        network_service = NetworkService(db)
        metrics = await network_service.get_bandwidth_metrics(
            network_id=network_id,
            interface=interface,
            hours=hours
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to get bandwidth metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve bandwidth metrics")


@router.get("/monitor/connectivity")
async def check_network_connectivity(
    targets: List[str] = Query(...),
    timeout: int = Query(5, ge=1, le=30),
    ray_manager = Depends(get_ray_manager)
):
    """Check connectivity to multiple targets using GPU acceleration"""
    try:
        if not ray.is_initialized():
            raise HTTPException(status_code=503, detail="Ray cluster not available")
        
        scanner_service = NetworkScannerService(ray_manager)
        results = await scanner_service.check_connectivity(
            targets=targets,
            timeout=timeout
        )
        
        return {
            "connectivity_results": results,
            "total_targets": len(targets),
            "timestamp": "now"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check connectivity: {e}")
        raise HTTPException(status_code=500, detail="Failed to check network connectivity")


@router.post("/port-scan")
async def port_scan(
    target: str,
    ports: List[int] = Query(None),
    port_range: Optional[str] = Query(None),  # e.g., "1-1000"
    scan_type: str = Query("tcp", regex="^(tcp|udp|syn)$"),
    ray_manager = Depends(get_ray_manager)
):
    """Perform port scan on target using GPU acceleration"""
    try:
        if not ray.is_initialized():
            raise HTTPException(status_code=503, detail="Ray cluster not available")
        
        scanner_service = NetworkScannerService(ray_manager)
        scan_id = await scanner_service.start_port_scan(
            target=target,
            ports=ports,
            port_range=port_range,
            scan_type=scan_type
        )
        
        return {
            "scan_id": scan_id,
            "message": "Port scan initiated",
            "target": target,
            "scan_type": scan_type,
            "estimated_duration": "1-10 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start port scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate port scan")


@router.get("/security/vulnerabilities")
async def scan_vulnerabilities(
    target: str,
    scan_depth: str = Query("basic", regex="^(basic|full|aggressive)$"),
    ray_manager = Depends(get_ray_manager)
):
    """Scan for network vulnerabilities using GPU acceleration"""
    try:
        if not ray.is_initialized():
            raise HTTPException(status_code=503, detail="Ray cluster not available")
        
        scanner_service = NetworkScannerService(ray_manager)
        vuln_scan_id = await scanner_service.start_vulnerability_scan(
            target=target,
            scan_depth=scan_depth
        )
        
        return {
            "vulnerability_scan_id": vuln_scan_id,
            "message": "Vulnerability scan initiated",
            "target": target,
            "scan_depth": scan_depth,
            "estimated_duration": "5-30 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start vulnerability scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate vulnerability scan")
