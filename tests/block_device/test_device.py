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
async def test_configure_coiot_protocol_sends_correct_parameters(
    mock_block_device: BlockDevice,
) -> None:
    """Test that configure_coiot_protocol calls http_request with expected params."""
    mock_block_device.http_request = AsyncMock()

    test_address = "10.10.10.10"
    test_port = 5683

    await mock_block_device.configure_coiot_protocol(test_address, test_port)

    mock_block_device.http_request.assert_awaited_once_with(
        "post",
        "settings/advanced",
        {
            "coiot_enable": "true",
            "coiot_peer": f"{test_address}:{test_port}",
        },
    )


@pytest.mark.asyncio
async def test_configure_coiot_protocol_propagates_exceptions(
    mock_block_device: BlockDevice,
) -> None:
    """Test that exceptions from http_request bubble up (no silent swallow)."""
    mock_block_device.http_request = AsyncMock(side_effect=RuntimeError("HTTP failure"))

    with pytest.raises(RuntimeError):
        await mock_block_device.configure_coiot_protocol("10.10.10.10", 5683)
