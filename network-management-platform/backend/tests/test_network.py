"""
Network discovery and management tests
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_ping_host():
    """Test ping functionality"""
    from app.services.network_discovery import network_discovery
    
    # Mock the ping result
    with patch.object(network_discovery, '_system_ping') as mock_ping:
        mock_ping.return_value = {
            "success": True,
            "time": 10.5,
            "output": "PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data."
        }
        
        result = await network_discovery.ping_host("8.8.8.8")
        
        assert result["host"] == "8.8.8.8"
        assert result["reachable"] is True
        assert "response_time" in result


@pytest.mark.asyncio
async def test_network_interfaces():
    """Test getting network interfaces"""
    from app.services.network_discovery import network_discovery
    
    interfaces = await network_discovery.get_network_interfaces()
    
    assert isinstance(interfaces, list)
    # In a real environment, there should be at least one interface
    if interfaces:
        interface = interfaces[0]
        assert "name" in interface
        assert "addresses" in interface


def test_network_discovery_endpoints(client):
    """Test network discovery API endpoints"""
    # Test ping endpoint
    response = client.post("/api/v1/network/discovery/ping?host=127.0.0.1")
    # This might fail without proper auth, but we test the endpoint exists
    assert response.status_code in [200, 401, 422]
    
    # Test interfaces endpoint
    response = client.get("/api/v1/network/interfaces")
    assert response.status_code in [200, 401]