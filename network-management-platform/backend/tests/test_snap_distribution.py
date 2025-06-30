"""
Tests for Snap Distribution Service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.snap_distribution_service import (
    SnapDistributionService,
    SnapDistribution,
    SnapChannel,
    RolloutPolicy,
    RolloutStrategy,
    ChannelRisk,
    SnapStoreProxyClient
)


class TestSnapDistributionService:
    """Test cases for SnapDistributionService"""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        return SnapDistributionService()
    
    @pytest.fixture
    def sample_distribution(self):
        """Create sample distribution for testing"""
        return SnapDistribution(
            snap_name="test-snap",
            source_channel=SnapChannel(track="latest", risk=ChannelRisk.CANDIDATE),
            target_channel=SnapChannel(track="latest", risk=ChannelRisk.STABLE),
            target_devices=["device-1", "device-2", "device-3"],
            rollout_policy=RolloutPolicy(
                strategy=RolloutStrategy.PROGRESSIVE,
                phases=[33, 66, 100],
                phase_duration_hours=1
            ),
            created_by="test-user"
        )
    
    def test_snap_channel_full_name(self):
        """Test SnapChannel full_name property"""
        # Test basic channel
        channel = SnapChannel(track="latest", risk=ChannelRisk.STABLE)
        assert channel.full_name == "latest/stable"
        
        # Test channel with branch
        channel_with_branch = SnapChannel(
            track="2.0", 
            risk=ChannelRisk.BETA, 
            branch="feature-x"
        )
        assert channel_with_branch.full_name == "2.0/beta/feature-x"
    
    @pytest.mark.asyncio
    async def test_service_start_stop(self, service):
        """Test service lifecycle"""
        assert not service.running
        
        await service.start()
        assert service.running
        
        await service.stop()
        assert not service.running
    
    @pytest.mark.asyncio
    async def test_validate_target_devices(self, service):
        """Test device validation"""
        device_ids = ["device-1", "device-2", "invalid-device"]
        
        # Mock snapd_service to simulate device validation
        with patch('app.services.snap_distribution_service.snapd_service') as mock_snapd:
            # Mock successful connection for valid devices
            mock_connection = AsyncMock()
            mock_snapd.get_connection.side_effect = [
                mock_connection,  # device-1: valid
                mock_connection,  # device-2: valid
                Exception("Device not found")  # invalid-device: invalid
            ]
            
            valid_devices = await service._validate_target_devices(device_ids)
            
            assert valid_devices == ["device-1", "device-2"]
            assert len(valid_devices) == 2
    
    @pytest.mark.asyncio
    async def test_create_distribution(self, service, sample_distribution):
        """Test distribution creation"""
        # Mock dependencies
        with patch('app.services.snap_distribution_service.cache_manager') as mock_cache, \
             patch('app.services.snap_distribution_service.websocket_manager') as mock_ws, \
             patch.object(service, '_validate_target_devices') as mock_validate:
            
            mock_validate.return_value = sample_distribution.target_devices
            mock_cache.set = AsyncMock()
            mock_ws.broadcast_system_event = AsyncMock()
            
            distribution_id = await service.create_distribution(sample_distribution)
            
            # Verify distribution was created
            assert distribution_id in service.active_distributions
            assert distribution_id in service.rollout_status
            
            # Verify cache was updated
            mock_cache.set.assert_called()
            
            # Verify websocket broadcast
            mock_ws.broadcast_system_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_progressive_rollout_phases(self, service, sample_distribution):
        """Test progressive rollout phase calculation"""
        # Mock dependencies
        with patch('app.services.snap_distribution_service.cache_manager') as mock_cache, \
             patch('app.services.snap_distribution_service.websocket_manager') as mock_ws, \
             patch('app.services.snap_distribution_service.snapd_service') as mock_snapd, \
             patch.object(service, '_validate_target_devices') as mock_validate:
            
            mock_validate.return_value = sample_distribution.target_devices
            mock_cache.set = AsyncMock()
            mock_ws.broadcast_system_event = AsyncMock()
            mock_snapd.install_snap_on_device = AsyncMock(return_value="change-123")
            
            # Create distribution
            distribution_id = await service.create_distribution(sample_distribution)
            
            # Verify rollout status
            rollout = service.rollout_status[distribution_id]
            assert rollout.current_phase == 0
            assert rollout.devices_targeted == 3
            assert rollout.status == "active"
    
    @pytest.mark.asyncio
    async def test_pause_resume_distribution(self, service, sample_distribution):
        """Test pausing and resuming distributions"""
        with patch('app.services.snap_distribution_service.cache_manager') as mock_cache, \
             patch('app.services.snap_distribution_service.websocket_manager') as mock_ws, \
             patch.object(service, '_validate_target_devices') as mock_validate:
            
            mock_validate.return_value = sample_distribution.target_devices
            mock_cache.set = AsyncMock()
            mock_ws.broadcast_system_event = AsyncMock()
            
            # Create distribution
            distribution_id = await service.create_distribution(sample_distribution)
            
            # Test pause
            await service.pause_distribution(distribution_id)
            rollout = service.rollout_status[distribution_id]
            assert rollout.status == "paused"
            
            # Test resume
            await service.resume_distribution(distribution_id)
            rollout = service.rollout_status[distribution_id]
            assert rollout.status == "active"
    
    @pytest.mark.asyncio
    async def test_rollback_distribution(self, service, sample_distribution):
        """Test distribution rollback"""
        with patch('app.services.snap_distribution_service.cache_manager') as mock_cache, \
             patch('app.services.snap_distribution_service.websocket_manager') as mock_ws, \
             patch('app.services.snap_distribution_service.snapd_service') as mock_snapd, \
             patch.object(service, '_validate_target_devices') as mock_validate, \
             patch.object(service, '_get_updated_devices') as mock_updated:
            
            mock_validate.return_value = sample_distribution.target_devices
            mock_cache.set = AsyncMock()
            mock_ws.broadcast_system_event = AsyncMock()
            mock_snapd.revert_snap_on_device = AsyncMock(return_value="revert-123")
            mock_updated.return_value = ["device-1", "device-2"]
            
            # Create distribution
            distribution_id = await service.create_distribution(sample_distribution)
            
            # Test rollback
            await service.rollback_distribution(distribution_id)
            
            rollout = service.rollout_status[distribution_id]
            assert rollout.status == "rolled_back"
            
            # Verify revert was called for updated devices
            assert mock_snapd.revert_snap_on_device.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_distribution_status(self, service, sample_distribution):
        """Test getting distribution status"""
        with patch('app.services.snap_distribution_service.cache_manager') as mock_cache, \
             patch('app.services.snap_distribution_service.websocket_manager') as mock_ws, \
             patch.object(service, '_validate_target_devices') as mock_validate:
            
            mock_validate.return_value = sample_distribution.target_devices
            mock_cache.set = AsyncMock()
            mock_ws.broadcast_system_event = AsyncMock()
            
            # Create distribution
            distribution_id = await service.create_distribution(sample_distribution)
            
            # Get status
            status = await service.get_distribution_status(distribution_id)
            
            assert status['distribution_id'] == distribution_id
            assert status['snap_name'] == sample_distribution.snap_name
            assert status['devices_targeted'] == 3
            assert status['current_phase'] == 0
            assert 'progress_percent' in status
    
    def test_invalid_distribution_operations(self, service):
        """Test operations on non-existent distributions"""
        invalid_id = "non-existent-id"
        
        # Test pause on invalid distribution
        with pytest.raises(ValueError):
            asyncio.run(service.pause_distribution(invalid_id))
        
        # Test resume on invalid distribution
        with pytest.raises(ValueError):
            asyncio.run(service.resume_distribution(invalid_id))
        
        # Test rollback on invalid distribution
        with pytest.raises(ValueError):
            asyncio.run(service.rollback_distribution(invalid_id))
        
        # Test get status on invalid distribution
        with pytest.raises(ValueError):
            asyncio.run(service.get_distribution_status(invalid_id))


class TestSnapStoreProxyClient:
    """Test cases for SnapStoreProxyClient"""
    
    @pytest.fixture
    def proxy_client(self):
        """Create proxy client for testing"""
        return SnapStoreProxyClient("http://proxy.example.com", "test-token")
    
    @pytest.mark.asyncio
    async def test_proxy_connection(self, proxy_client):
        """Test proxy connection establishment"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value = mock_session_instance
            
            await proxy_client.connect()
            
            assert proxy_client.session is not None
            mock_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_configure_device_proxy(self, proxy_client):
        """Test device proxy configuration"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "configured"})
            mock_session_instance.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value = mock_session_instance
            
            proxy_client.session = mock_session_instance
            
            config = {"proxy_url": "http://proxy.example.com"}
            result = await proxy_client.configure_device_proxy("device-1", config)
            
            assert result == {"status": "configured"}
            mock_session_instance.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_cached_snaps(self, proxy_client):
        """Test getting cached snaps from proxy"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=[
                {"name": "firefox", "revision": "123"},
                {"name": "code", "revision": "456"}
            ])
            mock_session_instance.get.return_value.__aenter__.return_value = mock_response
            mock_session.return_value = mock_session_instance
            
            proxy_client.session = mock_session_instance
            
            cached_snaps = await proxy_client.get_cached_snaps()
            
            assert len(cached_snaps) == 2
            assert cached_snaps[0]["name"] == "firefox"
            mock_session_instance.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pin_snap_revision(self, proxy_client):
        """Test pinning snap revision"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "pinned"})
            mock_session_instance.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value = mock_session_instance
            
            proxy_client.session = mock_session_instance
            
            result = await proxy_client.pin_snap_revision("firefox", "stable", "123")
            
            assert result == {"status": "pinned"}
            mock_session_instance.post.assert_called_once()


class TestRolloutPolicy:
    """Test cases for RolloutPolicy"""
    
    def test_default_rollout_policy(self):
        """Test default rollout policy creation"""
        policy = RolloutPolicy(strategy=RolloutStrategy.PROGRESSIVE)
        
        assert policy.strategy == RolloutStrategy.PROGRESSIVE
        assert policy.phases == [10, 30, 70, 100]
        assert policy.phase_duration_hours == 24
        assert policy.rollback_threshold_percent == 5.0
        assert policy.health_check_enabled is True
        assert policy.approval_required is False
    
    def test_custom_rollout_policy(self):
        """Test custom rollout policy creation"""
        policy = RolloutPolicy(
            strategy=RolloutStrategy.CANARY,
            phases=[5, 100],
            phase_duration_hours=12,
            rollback_threshold_percent=2.0,
            health_check_enabled=False,
            approval_required=True,
            target_groups=["production"],
            exclude_groups=["development"]
        )
        
        assert policy.strategy == RolloutStrategy.CANARY
        assert policy.phases == [5, 100]
        assert policy.phase_duration_hours == 12
        assert policy.rollback_threshold_percent == 2.0
        assert policy.health_check_enabled is False
        assert policy.approval_required is True
        assert policy.target_groups == ["production"]
        assert policy.exclude_groups == ["development"]


def test_service_integration():
    """Integration test for snap distribution service"""
    # This would be an integration test that tests the full workflow
    # with real dependencies. For now, we'll keep it as a placeholder.
    pass


if __name__ == "__main__":
    pytest.main([__file__])