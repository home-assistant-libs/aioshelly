"""Tests for block_device.device module."""

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from aiohttp.client import ClientSession
from bleak.backends.device import BLEDevice

from aioshelly.block_device import COAP, BlockDevice
from aioshelly.common import ConnectionOptions


@pytest.mark.asyncio
async def test_incorrect_shutdown(
    client_session: ClientSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multiple shutdown calls at incorrect order.

    https://github.com/home-assistant-libs/aioshelly/pull/535
    """
    coap_context = COAP()
    coap_context.sock = Mock(spec=socket.socket)
    coap_context.transport = Mock(spec=asyncio.DatagramTransport)
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device1 = await BlockDevice.create(client_session, coap_context, options)
    block_device2 = await BlockDevice.create(client_session, coap_context, options)

    # shutdown for device2 remove subscription for device1 from ws_context
    await block_device2.shutdown()

    assert "error during shutdown: KeyError('DDEEFF')" not in caplog.text

    await block_device1.shutdown()

    assert "error during shutdown: KeyError('DDEEFF')" in caplog.text


def test_block_device_requires_ip_address(client_session: ClientSession) -> None:
    """Test that BlockDevice requires ip_address."""
    coap_context = COAP()
    ble_device = MagicMock(spec=BLEDevice)
    options = ConnectionOptions(ble_device=ble_device)

    with pytest.raises(ValueError, match="Block devices require ip_address"):
        BlockDevice(coap_context, client_session, options)


@pytest.mark.asyncio
async def test_block_device_ip_address_property_guard(
    client_session: ClientSession,
) -> None:
    """Test ip_address property guard when ip_address is None."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device = BlockDevice(coap_context, client_session, options)

    # Manually set ip_address to None to test the property guard
    # This shouldn't happen in normal operation due to __init__ check
    block_device.options.ip_address = None

    with pytest.raises(RuntimeError, match="Block device ip_address is None"):
        _ = block_device.ip_address


@pytest.mark.asyncio
async def test_block_device_set_auth(
    client_session: ClientSession,
) -> None:
    """Test BlockDevice set_auth method."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device = BlockDevice(coap_context, client_session, options)
    block_device.http_request = AsyncMock(
        return_value={"enabled": True, "unprotected": False, "username": "admin"}
    )
    block_device._shelly = {"auth": False}

    result = await block_device.set_auth(True, "admin", "password123")

    block_device.http_request.assert_called_once_with(
        "get",
        "settings/login",
        {"enabled": True, "username": "admin", "password": "password123"},
    )
    assert result["enabled"] is True


@pytest.mark.asyncio
async def test_block_device_disable_auth(
    client_session: ClientSession,
) -> None:
    """Test BlockDevice disable_auth method."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device = BlockDevice(coap_context, client_session, options)
    block_device.http_request = AsyncMock(
        return_value={"enabled": False, "unprotected": True, "username": "admin"}
    )
    block_device._shelly = {"auth": True}

    result = await block_device.set_auth(False)

    block_device.http_request.assert_called_once_with(
        "get",
        "settings/login",
        {"enabled": False, "unprotected": True},
    )
    assert result["enabled"] is False


@pytest.mark.asyncio
async def test_block_device_set_auth_username_too_long(
    client_session: ClientSession,
) -> None:
    """Test BlockDevice set_auth with username too long."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device = BlockDevice(coap_context, client_session, options)

    with pytest.raises(
        ValueError, match="username must be between 1 and 50 characters"
    ):
        await block_device.set_auth(True, "a" * 51, "password123")


@pytest.mark.asyncio
async def test_block_device_set_auth_password_too_long(
    client_session: ClientSession,
) -> None:
    """Test BlockDevice set_auth with password too long."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device = BlockDevice(coap_context, client_session, options)

    with pytest.raises(
        ValueError, match="password must be between 1 and 50 characters"
    ):
        await block_device.set_auth(True, "admin", "a" * 51)
