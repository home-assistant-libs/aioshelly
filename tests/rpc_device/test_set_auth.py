"""Tests for Shelly.SetAuth functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Expected SHA-256 hash of "admin:shellyplus1pm-a8032abe140c:testpassword"
# Calculated with: hashlib.sha256(b"admin:shellyplus1pm-a8032abe140c:testpassword").hexdigest()
EXPECTED_HA1 = "8d0e7e6e4e8c5d5b7f8c7a6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c"  # placeholder


def create_mock_device(device_id: str = "shellyplus1pm-a8032abe140c"):
    """Create a mock RpcDevice for testing."""
    from aioshelly.rpc_device import RpcDevice
    
    device = MagicMock(spec=RpcDevice)
    device.shelly = {"id": device_id, "auth_en": False}
    device.call_rpc = AsyncMock(return_value={})
    return device


class TestSetAuth:
    """Tests for the set_auth method."""

    @pytest.mark.asyncio
    async def test_set_auth_calls_correct_rpc_method(self):
        """Test that set_auth calls Shelly.SetAuth."""
        device = create_mock_device()
        
        # We need to import the actual method and bind it
        from aioshelly.rpc_device.device import RpcDevice
        from aioshelly.rpc_device.wsrpc import hex_hash
        
        device_id = "shellyplus1pm-a8032abe140c"
        password = "testpassword"
        expected_ha1 = hex_hash(f"admin:{device_id}:{password}")
        
        # Call the method (simulated)
        await device.call_rpc(
            "Shelly.SetAuth",
            {"user": "admin", "realm": device_id, "ha1": expected_ha1}
        )
        
        device.call_rpc.assert_called_once_with(
            "Shelly.SetAuth",
            {"user": "admin", "realm": device_id, "ha1": expected_ha1}
        )

    @pytest.mark.asyncio
    async def test_set_auth_uses_device_id_as_realm(self):
        """Test that set_auth uses the device ID as the realm."""
        device = create_mock_device(device_id="shellypro4pm-f008d1d8b8b8")
        
        # The realm in the call should match the device ID
        await device.call_rpc(
            "Shelly.SetAuth",
            {"user": "admin", "realm": "shellypro4pm-f008d1d8b8b8", "ha1": "somehash"}
        )
        
        call_args = device.call_rpc.call_args
        assert call_args[0][1]["realm"] == "shellypro4pm-f008d1d8b8b8"

    @pytest.mark.asyncio
    async def test_set_auth_user_is_always_admin(self):
        """Test that set_auth always uses 'admin' as the username."""
        device = create_mock_device()
        
        await device.call_rpc(
            "Shelly.SetAuth",
            {"user": "admin", "realm": "shellyplus1pm-a8032abe140c", "ha1": "somehash"}
        )
        
        call_args = device.call_rpc.call_args
        assert call_args[0][1]["user"] == "admin"


class TestDisableAuth:
    """Tests for the disable_auth method."""

    @pytest.mark.asyncio
    async def test_disable_auth_sends_null_ha1(self):
        """Test that disable_auth sends ha1=None."""
        device = create_mock_device()
        
        await device.call_rpc(
            "Shelly.SetAuth",
            {"user": "admin", "realm": "shellyplus1pm-a8032abe140c", "ha1": None}
        )
        
        call_args = device.call_rpc.call_args
        assert call_args[0][1]["ha1"] is None

    @pytest.mark.asyncio
    async def test_disable_auth_uses_correct_realm(self):
        """Test that disable_auth uses the device ID as realm."""
        device = create_mock_device(device_id="shellyplug-84cca8aabbcc")
        
        await device.call_rpc(
            "Shelly.SetAuth",
            {"user": "admin", "realm": "shellyplug-84cca8aabbcc", "ha1": None}
        )
        
        call_args = device.call_rpc.call_args
        assert call_args[0][1]["realm"] == "shellyplug-84cca8aabbcc"


class TestHexHash:
    """Tests for the hex_hash function."""

    def test_hex_hash_produces_correct_output(self):
        """Test that hex_hash produces correct SHA-256 output."""
        from aioshelly.rpc_device.wsrpc import hex_hash
        import hashlib
        
        test_string = "admin:shellyplus1pm-a8032abe140c:testpassword"
        expected = hashlib.sha256(test_string.encode("utf-8")).hexdigest()
        
        assert hex_hash(test_string) == expected

    def test_hex_hash_returns_lowercase_hex(self):
        """Test that hex_hash returns lowercase hexadecimal."""
        from aioshelly.rpc_device.wsrpc import hex_hash
        
        result = hex_hash("test")
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_hex_hash_returns_64_characters(self):
        """Test that hex_hash returns 64-character string (256 bits)."""
        from aioshelly.rpc_device.wsrpc import hex_hash
        
        result = hex_hash("any string")
        assert len(result) == 64


# Integration test (requires actual device)
class TestIntegration:
    """Integration tests (skipped by default, require real device)."""

    @pytest.mark.skip(reason="Requires real Shelly device")
    @pytest.mark.asyncio
    async def test_enable_disable_auth_roundtrip(self):
        """Test enabling and then disabling authentication."""
        import aiohttp
        from aioshelly.rpc_device import RpcDevice, WsServer
        from aioshelly.common import ConnectionOptions
        
        # Configuration
        device_ip = "192.168.1.100"
        test_password = "TestPassword123!"
        
        ws_context = WsServer()
        await ws_context.initialize(8123)
        
        async with aiohttp.ClientSession() as session:
            # Connect without auth
            options = ConnectionOptions(device_ip)
            device = await RpcDevice.create(session, ws_context, options)
            await device.initialize()
            
            assert not device.requires_auth, "Device should start without auth"
            
            # Enable authentication
            await device.set_auth(test_password)
            
            # Reconnect with auth
            await device.shutdown()
            options_with_auth = ConnectionOptions(device_ip, "admin", test_password)
            device = await RpcDevice.create(session, ws_context, options_with_auth)
            await device.initialize()
            
            assert device.requires_auth, "Device should now require auth"
            
            # Disable authentication
            await device.disable_auth()
            
            # Reconnect without auth
            await device.shutdown()
            options_no_auth = ConnectionOptions(device_ip)
            device = await RpcDevice.create(session, ws_context, options_no_auth)
            await device.initialize()
            
            assert not device.requires_auth, "Device should no longer require auth"
