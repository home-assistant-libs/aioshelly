"""Tests for server-side RPC over Shelly outbound WebSockets."""

import asyncio
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import WSMsgType
from aiohttp.web import WebSocketResponse

from aioshelly.exceptions import (
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    RpcCallError,
)
from aioshelly.json import json_loads
from aioshelly.rpc_device.wsrpc import WsServer, WsServerConnection


def make_websocket() -> MagicMock:
    """Create a mocked server WebSocket."""
    websocket = MagicMock(spec=WebSocketResponse)
    websocket.closed = False
    websocket.send_frame = AsyncMock()
    websocket.close = AsyncMock()
    return websocket


@pytest.mark.asyncio
async def test_server_connection_rpc_call() -> None:
    """Test an RPC request and response over an inbound WebSocket."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )

    call_task = asyncio.create_task(
        connection.call("Switch.Set", {"id": 0, "on": True})
    )
    await asyncio.sleep(0)

    websocket.send_frame.assert_awaited_once()
    payload, opcode = websocket.send_frame.await_args.args
    request = json_loads(payload)

    assert opcode is WSMsgType.TEXT
    assert request["method"] == "Switch.Set"
    assert request["params"] == {"id": 0, "on": True}
    assert request["dst"] == "shellypro1pm-aabbccddeeff"
    assert request["src"].startswith("aios-")

    assert connection.handle_frame(
        {
            "id": request["id"],
            "src": "shellypro1pm-aabbccddeeff",
            "dst": request["src"],
            "result": {"was_on": False},
        }
    )
    assert await call_task == {"was_on": False}


@pytest.mark.asyncio
async def test_server_connection_ignores_notification_for_pending_calls() -> None:
    """Test notifications are left for the existing subscription path."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )

    assert not connection.handle_frame(
        {
            "src": "shellypro1pm-aabbccddeeff",
            "method": "NotifyStatus",
            "params": {"switch:0": {"output": True}},
        }
    )


@pytest.mark.asyncio
async def test_server_connection_rpc_error() -> None:
    """Test an RPC error from a remote device."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )

    call_task = asyncio.create_task(connection.call("Switch.Set", {"id": 0, "on": True}))
    await asyncio.sleep(0)
    payload = json_loads(websocket.send_frame.await_args.args[0])

    connection.handle_frame(
        {
            "id": payload["id"],
            "src": "shellypro1pm-aabbccddeeff",
            "error": {"code": 404, "message": "Not Found"},
        }
    )

    with pytest.raises(RpcCallError, match="Not Found"):
        await call_task


@pytest.mark.asyncio
async def test_server_connection_unauthorized() -> None:
    """Test a 401 response raises InvalidAuthError."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )

    call_task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    payload = json_loads(websocket.send_frame.await_args.args[0])

    connection.handle_frame(
        {
            "id": payload["id"],
            "src": "shellypro1pm-aabbccddeeff",
            "error": {
                "code": HTTPStatus.UNAUTHORIZED.value,
                "message": "Unauthorized",
            },
        }
    )

    with pytest.raises(InvalidAuthError, match="Unauthorized"):
        await call_task


@pytest.mark.asyncio
async def test_server_connection_timeout() -> None:
    """Test timeout waiting for a remote RPC response."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )

    with pytest.raises(DeviceConnectionTimeoutError):
        await connection.call("Shelly.GetStatus", timeout=0.001)

    assert connection._calls == {}


@pytest.mark.asyncio
async def test_server_connection_disconnect_fails_pending_call() -> None:
    """Test a disconnected remote WebSocket fails pending calls."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )

    call_task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    connection.mark_disconnected()

    with pytest.raises(DeviceConnectionError):
        await call_task

    assert not connection.connected
    assert connection._calls == {}


@pytest.mark.asyncio
async def test_ws_server_calls_registered_connection() -> None:
    """Test WsServer delegates RPC calls to a registered inbound connection."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )
    server = WsServer()
    server.connections["AABBCCDDEEFF"] = connection

    call_task = asyncio.create_task(server.call("aabbccddeeff", "Shelly.GetStatus"))
    await asyncio.sleep(0)
    payload = json_loads(websocket.send_frame.await_args.args[0])
    connection.handle_frame(
        {
            "id": payload["id"],
            "src": "shellypro1pm-aabbccddeeff",
            "result": {"switch:0": {"output": True}},
        }
    )

    assert await call_task == {"switch:0": {"output": True}}


@pytest.mark.asyncio
async def test_ws_server_call_without_connection() -> None:
    """Test RPC call without an active inbound connection."""
    server = WsServer()

    with pytest.raises(DeviceConnectionError, match="No active inbound WebSocket"):
        await server.call("AABBCCDDEEFF", "Shelly.GetStatus")
