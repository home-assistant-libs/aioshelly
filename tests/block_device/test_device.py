"""Tests for block_device.device module."""

import asyncio
import socket
from unittest.mock import Mock

import pytest
from aiohttp.client import ClientSession

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
