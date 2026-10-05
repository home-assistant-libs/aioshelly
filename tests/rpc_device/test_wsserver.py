"""Tests for server-side RPC over Shelly outbound WebSockets."""

import asyncio
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import WSMsgType
from aiohttp.web import WebSocketResponse

from aioshelly.common import ConnectionOptions
from aioshelly.exceptions import (
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    RpcCallError,
)
from aioshelly.json import json_dumps, json_loads
from aioshelly.rpc_device.device import RpcDevice, RpcUpdateType
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

    call_task = asyncio.create_task(
        connection.call("Switch.Set", {"id": 0, "on": True})
    )
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


@pytest.mark.asyncio
async def test_server_connection_auth_retry() -> None:
    """Test digest authentication retry over an inbound WebSocket."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )
    connection.set_auth_data(
        "shellypro1pm-aabbccddeeff",
        "admin",
        "secret",
    )

    call_task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)

    first_request = json_loads(websocket.send_frame.await_args_list[0].args[0])
    assert "auth" not in first_request

    challenge = {
        "auth_type": "digest",
        "nonce": "test-nonce",
        "nc": 1,
        "realm": "shellypro1pm-aabbccddeeff",
        "algorithm": "SHA-256",
    }
    connection.handle_frame(
        {
            "id": first_request["id"],
            "src": "shellypro1pm-aabbccddeeff",
            "error": {
                "code": HTTPStatus.UNAUTHORIZED.value,
                "message": json_dumps(challenge),
            },
        }
    )
    await asyncio.sleep(0)

    assert websocket.send_frame.await_count == 2
    second_request = json_loads(websocket.send_frame.await_args_list[1].args[0])
    assert second_request["auth"]["realm"] == "shellypro1pm-aabbccddeeff"
    assert second_request["auth"]["nonce"] == "test-nonce"

    connection.handle_frame(
        {
            "id": second_request["id"],
            "src": "shellypro1pm-aabbccddeeff",
            "result": {"switch:0": {"output": True}},
        }
    )

    assert await call_task == {"switch:0": {"output": True}}


@pytest.mark.asyncio
async def test_rpc_device_initializes_over_remote_connection() -> None:
    """Test RpcDevice initialization without an IP address."""
    websocket = make_websocket()
    connection = WsServerConnection(
        "AABBCCDDEEFF",
        "shellypro1pm-aabbccddeeff",
        websocket,
    )
    server = WsServer()
    server.connections["AABBCCDDEEFF"] = connection

    device_info = {
        "id": "shellypro1pm-aabbccddeeff",
        "mac": "AABBCCDDEEFF",
        "model": "SPSW-201PE16EU",
        "gen": 2,
        "fw_id": "20230101-000000/1.0.0",
        "ver": "1.0.0",
        "auth_en": False,
    }
    config = {"sys": {"device": {"name": "Remote Shelly"}}}
    status = {"sys": {"wakeup_period": 0}, "switch:0": {"output": False}}
    connection.calls = AsyncMock(
        side_effect=[
            [device_info],
            [config, status],
        ]
    )

    device = RpcDevice(
        server,
        None,
        ConnectionOptions(remote_device_id="aabbccddeeff"),
    )
    await device.initialize()

    assert device.initialized
    assert device.connected
    assert device.hostname == "shellypro1pm-aabbccddeeff"
    assert device.status["switch:0"]["output"] is False

    listener = MagicMock()
    device.subscribe_updates(listener)
    server.remote_subscriptions["AABBCCDDEEFF"](
        {
            "src": "shellypro1pm-aabbccddeeff",
            "method": "NotifyStatus",
            "params": {"switch:0": {"output": True}},
        }
    )

    assert device.status["switch:0"]["output"] is True
    listener.assert_called_once_with(device, RpcUpdateType.STATUS)


@pytest.mark.asyncio
async def test_ws_server_reuses_connection_object_after_reconnect() -> None:
    """Test the per-device transport survives WebSocket reconnects."""
    server = WsServer()
    connection = server.get_or_create_connection("aabbccddeeff")
    first_websocket = make_websocket()
    second_websocket = make_websocket()

    assert not connection.connected

    connection.attach("shellypro1pm-aabbccddeeff", first_websocket)
    assert connection.connected
    assert server.get_or_create_connection("AABBCCDDEEFF") is connection

    connection.mark_disconnected()
    assert not connection.connected

    connection.attach("shellypro1pm-aabbccddeeff", second_websocket)
    assert connection.connected
    assert server.get_or_create_connection("AABBCCDDEEFF") is connection


@pytest.mark.asyncio
@pytest.mark.parametrize("initialized", [True, False])
async def test_rpc_device_remote_connection_updates(initialized: bool) -> None:
    """Test remote connect and disconnect events reach RpcDevice listeners."""
    websocket = make_websocket()
    server = WsServer()
    connection = server.get_or_create_connection("AABBCCDDEEFF")
    connection.attach("shellypro1pm-aabbccddeeff", websocket)

    device_info = {
        "id": "shellypro1pm-aabbccddeeff",
        "mac": "AABBCCDDEEFF",
        "model": "SPSW-201PE16EU",
        "gen": 2,
        "fw_id": "20230101-000000/1.0.0",
        "ver": "1.0.0",
        "auth_en": False,
    }
    config = {"sys": {"device": {"name": "Remote Shelly"}}}
    status = {"sys": {"wakeup_period": 0}}
    connection.calls = AsyncMock(
        side_effect=[
            [device_info],
            [config, status],
        ]
    )

    device = RpcDevice(
        server,
        None,
        ConnectionOptions(remote_device_id="AABBCCDDEEFF"),
    )
    await device.initialize()

    listener = MagicMock()
    device.subscribe_updates(listener)

    server._notify_connection_update("AABBCCDDEEFF", False)
    listener.assert_called_once_with(device, RpcUpdateType.DISCONNECTED)

    listener.reset_mock()
    device.initialized = initialized
    server._notify_connection_update("AABBCCDDEEFF", True)
    listener.assert_called_once_with(device, RpcUpdateType.ONLINE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frame",
    [
        {"method": 42, "params": {}},
        {"method": "NotifyStatus", "params": []},
        {"method": "NotifyEvent", "params": None},
    ],
)
async def test_malformed_remote_notification_is_not_dispatched(frame: dict) -> None:
    """Reject malformed notifications before they reach a device listener."""
    server = WsServer()
    websocket, queue = make_streaming_websocket()
    listener = MagicMock()
    server.subscribe_remote_updates("AABBCCDDEEFF", listener)
    handler = asyncio.create_task(
        server.handle_connection(websocket, "AABBCCDDEEFF", "peer")
    )
    await queue.put(frame)
    await handler
    listener.assert_not_called()
    assert websocket.closed


@pytest.mark.asyncio
async def test_remote_timeout_does_not_expose_rpc_parameters() -> None:
    """A failed configuration call must not include sensitive URL parameters."""
    connection = WsServerConnection("AABBCCDDEEFF", "peer", make_websocket())
    with pytest.raises(DeviceConnectionTimeoutError) as error:
        await connection.call(
            "Ws.SetConfig",
            {"config": {"server": "wss://example.com?secret=credential"}},
            timeout=0.01,
        )
    assert "credential" not in repr(error.value)


@pytest.mark.asyncio
async def test_remote_disconnect_does_not_expose_rpc_parameters() -> None:
    """Pending calls fail without exposing their configuration parameters."""
    connection = WsServerConnection("AABBCCDDEEFF", "peer", make_websocket())
    call = asyncio.create_task(
        connection.call("Ws.SetConfig", {"config": {"server": "credential"}})
    )
    await asyncio.sleep(0)
    connection.mark_disconnected()
    with pytest.raises(DeviceConnectionError) as error:
        await call
    assert "credential" not in repr(error.value)


@pytest.mark.asyncio
async def test_concurrent_calls_correlate_out_of_order() -> None:
    """Match concurrent responses by ID, independently of their arrival order."""
    websocket = make_websocket()
    connection = WsServerConnection("AABBCCDDEEFF", "peer", websocket)
    first = asyncio.create_task(connection.call("Switch.Set", {"id": 0, "on": True}))
    second = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    requests = [
        json_loads(call.args[0]) for call in websocket.send_frame.await_args_list
    ]
    assert requests[0]["id"] != requests[1]["id"]
    assert not connection.handle_frame({"method": "NotifyStatus", "params": {}})
    assert not connection.handle_frame({"id": 987, "result": {}})
    connection.handle_frame({"id": requests[1]["id"], "result": {"output": True}})
    connection.handle_frame({"id": requests[0]["id"], "result": {"was_on": False}})
    assert await second == {"output": True}
    assert await first == {"was_on": False}
    assert connection._calls == {}


@pytest.mark.parametrize(
    "response",
    [{}, {"result": []}, {"error": []}, {"error": {"code": "401", "message": 0}}],
)
@pytest.mark.asyncio
async def test_invalid_rpc_responses(response: dict) -> None:
    """Malformed replies become RPC errors rather than uncaught type errors."""
    websocket = make_websocket()
    connection = WsServerConnection("AABBCCDDEEFF", "peer", websocket)
    task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    connection.handle_frame({"id": 1, **response})
    with pytest.raises(RpcCallError, match="bad response"):
        await task
    assert connection._calls == {}


@pytest.mark.parametrize("frame_id", [[], {}, "1", True, None])
@pytest.mark.asyncio
async def test_invalid_response_ids(frame_id: object) -> None:
    """Invalid IDs cannot crash dispatch or match a pending integer ID."""
    connection = WsServerConnection("AABBCCDDEEFF", "peer", make_websocket())
    assert not connection.handle_frame({"id": frame_id, "result": {}})


@pytest.mark.parametrize(
    "challenge",
    [
        "not-json",
        "[]",
        "{}",
        '{"realm":"wrong","nonce":"nonce","algorithm":"SHA-256"}',
        '{"realm":"peer","nonce":"nonce","algorithm":"MD5"}',
    ],
)
@pytest.mark.asyncio
async def test_invalid_auth_challenges(challenge: str) -> None:
    """Reject malformed or mismatched authentication challenges."""
    websocket = make_websocket()
    connection = WsServerConnection("AABBCCDDEEFF", "peer", websocket)
    connection.set_auth_data("peer", "admin", "secret")
    task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    connection.handle_frame({"id": 1, "error": {"code": 401, "message": challenge}})
    with pytest.raises(InvalidAuthError):
        await task
    assert connection._calls == {}


@pytest.mark.asyncio
async def test_stale_auth_retry_is_bounded() -> None:
    """Retry an expired nonce once, then reject repeated stale challenges."""
    websocket = make_websocket()
    connection = WsServerConnection("AABBCCDDEEFF", "peer", websocket)
    connection.set_auth_data("peer", "admin", "secret")
    challenge = {
        "realm": "peer",
        "nonce": "fresh",
        "algorithm": "SHA-256",
        "stale": True,
    }
    task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    connection.handle_frame(
        {"id": 1, "error": {"code": 401, "message": json_dumps(challenge)}}
    )
    await asyncio.sleep(0)
    retry = json_loads(websocket.send_frame.await_args_list[1].args[0])
    assert retry["auth"]["nonce"] == "fresh"
    connection.handle_frame(
        {"id": retry["id"], "error": {"code": 401, "message": json_dumps(challenge)}}
    )
    with pytest.raises(InvalidAuthError):
        await task
    assert websocket.send_frame.await_count == 2
    assert connection._calls == {}


@pytest.mark.asyncio
async def test_stale_auth_retry_success() -> None:
    """A fresh nonce restores operation after a stale challenge."""
    websocket = make_websocket()
    connection = WsServerConnection("AABBCCDDEEFF", "peer", websocket)
    connection.set_auth_data("peer", "admin", "secret")
    task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    challenge = {
        "realm": "peer",
        "nonce": "fresh",
        "algorithm": "SHA-256",
        "stale": True,
    }
    connection.handle_frame(
        {"id": 1, "error": {"code": 401, "message": json_dumps(challenge)}}
    )
    await asyncio.sleep(0)
    connection.handle_frame({"id": 2, "result": {"sys": {}}})
    assert await task == {"sys": {}}


@pytest.mark.asyncio
async def test_cancellation_and_send_error_clean_pending_calls() -> None:
    """Cancellation and send failures leave no pending futures behind."""
    websocket = make_websocket()
    connection = WsServerConnection("AABBCCDDEEFF", "peer", websocket)
    task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert connection._calls == {}
    websocket.send_frame.side_effect = ConnectionResetError
    with pytest.raises(DeviceConnectionError, match="send failed"):
        await connection.call("Shelly.GetStatus")
    assert connection._calls == {}


@pytest.mark.asyncio
async def test_auth_lock_is_included_in_timeout() -> None:
    """A blocked authentication queue respects the caller's timeout."""
    connection = WsServerConnection("AABBCCDDEEFF", "peer", make_websocket())
    connection.set_auth_data("peer", "admin", "secret")
    async with connection._auth_lock:
        with pytest.raises(DeviceConnectionTimeoutError):
            await connection.call("Shelly.GetStatus", timeout=0.001)
    assert connection._calls == {}


@pytest.mark.asyncio
async def test_reconnect_resets_auth_and_fails_old_calls() -> None:
    """A new socket cannot complete calls sent on the previous socket."""
    connection = WsServerConnection("AABBCCDDEEFF", "peer", make_websocket())
    connection.set_auth_data("peer", "admin", "secret")
    connection._session.auth_data.nonce = "old"
    task = asyncio.create_task(connection.call("Shelly.GetStatus"))
    await asyncio.sleep(0)
    connection.attach("peer", make_websocket())
    with pytest.raises(DeviceConnectionError):
        await task
    assert connection._session.auth_data.nonce == ""
    assert not connection.handle_frame({"id": 1, "result": {}})
    assert connection.connected


@pytest.mark.asyncio
async def test_remote_device_identity_mismatch() -> None:
    """Remote initialization verifies the requested identity without device_mac."""
    connection = WsServerConnection("AABBCCDDEEFF", "peer", make_websocket())
    connection.calls = AsyncMock(
        return_value=[{"mac": "112233445566", "auth_en": False}]
    )
    device = RpcDevice(
        None, None, ConnectionOptions(remote_device_id="AABBCCDDEEFF"), connection
    )
    from aioshelly.exceptions import MacAddressMismatchError  # noqa: PLC0415

    with pytest.raises(MacAddressMismatchError):
        await device.initialize()
    assert not device.connected


def make_streaming_websocket() -> tuple[MagicMock, asyncio.Queue]:
    """Create a WebSocket with a controlled inbound stream."""
    from aiohttp import WSMessage  # noqa: PLC0415

    queue: asyncio.Queue = asyncio.Queue()
    websocket = make_websocket()

    async def frames():  # noqa: ANN202
        while (frame := await queue.get()) is not None:
            yield WSMessage(WSMsgType.TEXT, json_dumps(frame), "")

    async def close() -> None:
        websocket.closed = True
        await queue.put(None)

    websocket.__aiter__.side_effect = frames
    websocket.close.side_effect = close
    return websocket, queue


@pytest.mark.asyncio
async def test_server_multiple_devices_and_reconnect() -> None:
    """Dispatch independent devices and reuse their transports on reconnect."""
    server = WsServer()
    first_socket, first_queue = make_streaming_websocket()
    second_socket, second_queue = make_streaming_websocket()
    updates = MagicMock()
    unsubscribe = server.subscribe_connection_updates(updates)
    notifications = MagicMock()
    server.subscribe_remote_updates("AABBCCDDEEFF", notifications)
    first_handler = asyncio.create_task(
        server.handle_connection(first_socket, "AABBCCDDEEFF", "peer-a")
    )
    second_handler = asyncio.create_task(
        server.handle_connection(second_socket, "112233445566", "peer-b")
    )
    await asyncio.sleep(0)
    connection = server.get_connection("AABBCCDDEEFF")
    first_call = asyncio.create_task(
        server.call("AABBCCDDEEFF", "Switch.Set", {"id": 0, "on": True})
    )
    second_call = asyncio.create_task(server.call("112233445566", "Shelly.GetStatus"))
    await asyncio.sleep(0)
    await first_queue.put({"method": "NotifyEvent", "params": {"events": []}})
    await first_queue.put({"id": 1, "result": {"was_on": False}})
    await second_queue.put({"id": 1, "result": {"sys": {}}})
    assert await first_call == {"was_on": False}
    assert await second_call == {"sys": {}}
    notifications.assert_called_once_with(
        {"method": "NotifyEvent", "params": {"events": []}}
    )
    replacement, replacement_queue = make_streaming_websocket()
    replacement_handler = asyncio.create_task(
        server.handle_connection(replacement, "AABBCCDDEEFF", "peer-a")
    )
    await asyncio.sleep(0)
    await first_handler
    assert server.get_connection("AABBCCDDEEFF") is connection
    assert connection.connected
    new_call = asyncio.create_task(server.call("AABBCCDDEEFF", "Shelly.GetConfig"))
    await asyncio.sleep(0)
    await replacement_queue.put({"id": 2, "result": {"sys": {}}})
    assert await new_call == {"sys": {}}
    await replacement.close()
    await second_socket.close()
    await asyncio.gather(replacement_handler, second_handler)
    assert not connection.connected
    assert updates.call_args_list[-2].args == ("AABBCCDDEEFF", False)
    unsubscribe()


@pytest.mark.asyncio
async def test_legacy_endpoint_cannot_attach_remote_transport() -> None:
    """The unauthenticated battery endpoint cannot change remote connections."""
    from unittest.mock import patch  # noqa: PLC0415

    server = WsServer()
    connection = server.get_or_create_connection("AABBCCDDEEFF")
    remote_listener = MagicMock()
    local_listener = MagicMock()
    server.subscribe_remote_updates("AABBCCDDEEFF", remote_listener)
    server.subscribe_updates("192.0.2.10", local_listener)
    websocket = make_websocket()
    from aiohttp import WSMessage  # noqa: PLC0415

    websocket.__aiter__.return_value = [
        WSMessage(
            WSMsgType.TEXT,
            json_dumps(
                {"src": "shelly-aabbccddeeff", "method": "NotifyStatus", "params": {}}
            ),
            "",
        )
    ]
    websocket.prepare = AsyncMock()
    request = MagicMock()
    request.remote = "192.0.2.10"
    with patch("aioshelly.rpc_device.wsrpc.WebSocketResponse", return_value=websocket):
        await server.websocket_handler(request)
    assert not connection.connected
    remote_listener.assert_not_called()
    local_listener.assert_called_once()
