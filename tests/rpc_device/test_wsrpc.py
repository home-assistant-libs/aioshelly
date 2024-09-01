"""Tests for rpc_device.device module."""

import pytest
from aiohttp.http_websocket import WSMessage, WSMsgType

from aioshelly.rpc_device.wsrpc import WsRPC

from .conftest import ResponseMocker


@pytest.mark.asyncio
async def test_device_wscall(
    ws_rpc: WsRPC, rpc_websocket_responses: ResponseMocker
) -> None:
    """Test wscall."""
    await rpc_websocket_responses.mock_ws_message(
        WSMessage(WSMsgType.TEXT, '{"id": 1, "result": {"a": 1}}', None)
    )
    await ws_rpc.call("Shelly.GetConfig")
