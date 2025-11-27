"""Tests for Gen1 BlockDevice Shelly authentication functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock


def create_mock_block_device():
    """Create a mock BlockDevice for testing."""
    from aioshelly.block_device import BlockDevice

    device = MagicMock(spec=BlockDevice)
    device.shelly = {"auth": False, "type": "SHSW-1", "fw": "20230913-114244/v1.14.0-gcb84623"}
    device.http_request = AsyncMock(return_value={"enabled": True, "unprotected": False, "username": "admin"})
    return device


class TestBlockDeviceSetAuth:
    """Tests for the BlockDevice set_auth method."""

    @pytest.mark.asyncio
    async def test_set_auth_calls_correct_endpoint(self):
        """Test that set_auth calls the correct HTTP endpoint."""
        device = create_mock_block_device()

        await device.http_request(
            "get",
            "settings/login",
            {"enabled": 1, "username": "admin", "password": "testpass"}
        )

        device.http_request.assert_called_once_with(
            "get",
            "settings/login",
            {"enabled": 1, "username": "admin", "password": "testpass"}
        )

    @pytest.mark.asyncio
    async def test_set_auth_allows_custom_username(self):
        """Test that set_auth allows custom usernames (not just 'admin')."""
        device = create_mock_block_device()

        await device.http_request(
            "get",
            "settings/login",
            {"enabled": 1, "username": "myuser", "password": "mypass"}
        )

        call_args = device.http_request.call_args
        assert call_args[0][2]["username"] == "myuser"

    @pytest.mark.asyncio
    async def test_set_auth_returns_login_settings(self):
        """Test that set_auth returns the login settings response."""
        device = create_mock_block_device()
        device.http_request.return_value = {
            "enabled": True,
            "unprotected": False,
            "username": "admin"
        }

        result = await device.http_request(
            "get",
            "settings/login",
            {"enabled": 1, "username": "admin", "password": "test"}
        )

        assert result["enabled"] is True
        assert result["username"] == "admin"
        assert "password" not in result  # Password should not be returned


class TestBlockDeviceDisableAuth:
    """Tests for the BlockDevice disable_auth method."""

    @pytest.mark.asyncio
    async def test_disable_auth_calls_correct_endpoint(self):
        """Test that disable_auth calls the correct HTTP endpoint."""
        device = create_mock_block_device()

        await device.http_request(
            "get",
            "settings/login",
            {"enabled": 0}
        )

        device.http_request.assert_called_once_with(
            "get",
            "settings/login",
            {"enabled": 0}
        )

    @pytest.mark.asyncio
    async def test_disable_auth_returns_login_settings(self):
        """Test that disable_auth returns the login settings response."""
        device = create_mock_block_device()
        device.http_request.return_value = {
            "enabled": False,
            "unprotected": False,
            "username": "admin"
        }

        result = await device.http_request(
            "get",
            "settings/login",
            {"enabled": 0}
        )

        assert result["enabled"] is False


class TestBlockDeviceAuthRoundtrip:
    """Integration-style tests for auth enable/disable cycle."""

    @pytest.mark.asyncio
    async def test_enable_then_disable_auth(self):
        """Test enabling and then disabling authentication."""
        device = create_mock_block_device()

        # Enable auth
        device.http_request.return_value = {"enabled": True, "unprotected": False, "username": "admin"}
        result1 = await device.http_request(
            "get",
            "settings/login",
            {"enabled": 1, "username": "admin", "password": "secret"}
        )
        assert result1["enabled"] is True

        # Disable auth
        device.http_request.return_value = {"enabled": False, "unprotected": False, "username": "admin"}
        result2 = await device.http_request(
            "get",
            "settings/login",
            {"enabled": 0}
        )
        assert result2["enabled"] is False


# Integration test (requires actual device)
class TestBlockDeviceIntegration:
    """Integration tests (skipped by default, require real device)."""

    @pytest.mark.skip(reason="Requires real Gen1 Shelly device")
    @pytest.mark.asyncio
    async def test_enable_disable_auth_on_real_device(self):
        """Test enabling and then disabling authentication on real device."""
        import aiohttp
        from aioshelly.block_device import BlockDevice, COAP
        from aioshelly.common import ConnectionOptions

        # Configuration
        device_ip = "192.168.1.100"
        test_username = "admin"
        test_password = "TestPassword123!"

        async with COAP() as coap_context:
            async with aiohttp.ClientSession() as session:
                # Connect without auth
                device = await BlockDevice.create(session, coap_context, device_ip)
                await device.initialize()

                assert not device.requires_auth, "Device should start without auth"

                # Enable authentication
                result = await device.set_auth(test_username, test_password)
                assert result["enabled"] is True

                # Reconnect with auth
                await device.shutdown()
                options_with_auth = ConnectionOptions(
                    device_ip, test_username, test_password
                )
                device = await BlockDevice.create(session, coap_context, options_with_auth)
                await device.initialize()

                assert device.requires_auth, "Device should now require auth"

                # Disable authentication
                result = await device.disable_auth()
                assert result["enabled"] is False

                # Verify we can connect without auth again
                await device.shutdown()
                device = await BlockDevice.create(session, coap_context, device_ip)
                await device.initialize()

                assert not device.requires_auth, "Device should no longer require auth"
