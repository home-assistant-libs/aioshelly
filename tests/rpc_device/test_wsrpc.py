"""Tests for rpc_device.wsrpc module."""

import asyncio
import gc
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import (
    ClientConnectionResetError,
    ClientError,
    ClientSession,
    ClientWebSocketResponse,
    WSServerHandshakeError,
)
from aiohttp.http_websocket import WSMessage, WSMsgType
from aiohttp.test_utils import TestClient, TestServer
from aiohttp.web import Application, get

from aioshelly.const import NOTIFY_WS_CLOSED, WS_API_URL
from aioshelly.exceptions import (
    ConnectionClosed,
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    InvalidMessage,
    RpcCallError,
)
from aioshelly.json import json_bytes, json_dumps
from aioshelly.rpc_device.wsrpc import (
    HA2,
    AuthData,
    RPCCall,
    RPCSource,
    SessionData,
    WsServer,
    _receive_json_or_raise,
    hex_hash,
)

from . import load_device_fixture
from .conftest import NotifyHistory, ResponseMocker, WsRPCMocker

LOGGER_NAME = "aioshelly.rpc_device.wsrpc"


def make_401_response(
    nonce: str,
    stale: bool = False,
    nc: int = 1,
) -> dict[str, Any]:
    """Build a 401 error response with JSON-encoded digest challenge."""
    challenge: dict[str, Any] = {
        "auth_type": "digest",
        "nonce": nonce,
        "nc": nc,
        "realm": "shellyplus2pm-aabbccddeeff",
        "algorithm": "SHA-256",
        "stale": stale,
    }
    return {
        "src": "shellyplus2pm-aabbccddeeff",
        "error": {"code": 401, "message": json_dumps(challenge)},
    }


def make_success_response(result: dict[str, Any]) -> dict[str, Any]:
    """Build a successful result response."""
    return {"src": "shellyplus2pm-aabbccddeeff", "result": result}


def test_receive_json_or_raise_text_returns_decoded_json() -> None:
    """Test text message with JSON payload returns decoded dict."""
    msg = WSMessage(WSMsgType.TEXT, b'{"key":"value","n":1}', None)

    assert _receive_json_or_raise(msg) == {"key": "value", "n": 1}


@pytest.mark.parametrize("data", [b"not-json", "not-json"])
def test_receive_json_or_raise_text_invalid_json_raises_invalid_message(
    data: bytes | str,
) -> None:
    """Test text message with invalid JSON raises InvalidMessage."""
    msg = WSMessage(WSMsgType.TEXT, data, None)

    with pytest.raises(InvalidMessage, match="Received invalid JSON: not-json"):
        _receive_json_or_raise(msg)


@pytest.mark.parametrize(
    "msg_type",
    [WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING],
)
def test_receive_json_or_raise_close_types_raise_connection_closed(
    msg_type: WSMsgType,
) -> None:
    """Test close-related message types raise ConnectionClosed."""
    msg = WSMessage(msg_type, None, None)

    with pytest.raises(ConnectionClosed, match="Connection was closed"):
        _receive_json_or_raise(msg)


def test_receive_json_or_raise_error_type_raises_invalid_message() -> None:
    """Test error message type raises InvalidMessage."""
    msg = WSMessage(WSMsgType.ERROR, None, None)

    with pytest.raises(InvalidMessage, match="Received message error"):
        _receive_json_or_raise(msg)


def test_receive_json_or_raise_non_text_type_raises_invalid_message() -> None:
    """Test non-text and non-close message type raises InvalidMessage."""
    msg = WSMessage(WSMsgType.BINARY, b"bytes", None)

    with pytest.raises(InvalidMessage, match="Received non-Text message"):
        _receive_json_or_raise(msg)


@pytest.mark.asyncio
async def test_device_wscall_get_config(ws_rpc: WsRPCMocker) -> None:
    """Test wscall."""
    config_response = await load_device_fixture("shellyplugus", "Shelly.GetConfig")
    calls = [("Shelly.GetConfig", None)]
    responses = [config_response]
    results = await ws_rpc.calls_with_mocked_responses(calls, responses)
    assert results[0] == config_response["result"]


@pytest.mark.asyncio
async def test_device_wscall_no_auth_retry(ws_rpc: WsRPCMocker) -> None:
    """Test wscall when auth is not set."""
    cover_close_auth_fail = await load_device_fixture(
        "shellyplus2pm", "Cover.Close_auth_failure"
    )
    cover_close_success = await load_device_fixture(
        "shellyplus2pm", "Cover.Close_success"
    )
    calls = [("Cover.Close", {"id": 0})]
    responses = [cover_close_auth_fail, cover_close_success]
    with pytest.raises(InvalidAuthError):
        await ws_rpc.calls_with_mocked_responses(calls, responses)


@pytest.mark.asyncio
async def test_device_wscall_auth_retry(ws_rpc_with_auth: WsRPCMocker) -> None:
    """Test wscall when auth is set and a retry works."""
    cover_close_auth_fail = await load_device_fixture(
        "shellyplus2pm", "Cover.Close_auth_failure"
    )
    cover_close_success = await load_device_fixture(
        "shellyplus2pm", "Cover.Close_success"
    )
    calls = [("Cover.Close", {"id": 0})]
    ws_rpc_with_auth.set_auth_data("auth_domain", "username", "password")
    responses = [cover_close_auth_fail, cover_close_success]
    results = await ws_rpc_with_auth.calls_with_mocked_responses(calls, responses)
    assert results[0] == cover_close_success["result"]


def test_auth_update_challenge_unsupported_algorithm() -> None:
    """Test challenge update raises when algorithm is unsupported."""
    auth_data = AuthData("auth_domain", "username", "password")

    with pytest.raises(InvalidAuthError, match="Unsupported auth algorithm: SHA-1"):
        auth_data.update_challenge({"nonce": "test_nonce", "algorithm": "SHA-1"})


@pytest.mark.asyncio
async def test_wscall_not_connected_without_auth(ws_rpc: WsRPCMocker) -> None:
    """Test call raises when websocket is not connected and auth is not set."""
    await ws_rpc.disconnect()

    with pytest.raises(RuntimeError, match="Not connected"):
        await ws_rpc.calls([("Shelly.GetConfig", None)])


@pytest.mark.asyncio
async def test_wscall_not_connected_with_auth(ws_rpc: WsRPCMocker) -> None:
    """Test call raises when websocket is not connected and auth is set."""
    await ws_rpc.disconnect()

    ws_rpc.set_auth_data("auth_domain", "username", "password")
    with pytest.raises(RuntimeError, match="Not connected"):
        await ws_rpc.calls([("Shelly.GetConfig", None)])


@pytest.mark.asyncio
async def test_disconnect_reraises_cancelled_error_when_caller_cancelled(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test disconnect re-raises CancelledError when the calling task is cancelled."""
    rx_task_cancelled = asyncio.Event()

    async def _rx_msgs() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            rx_task_cancelled.set()
            # Yield so the caller is still awaiting the rx task when cancelled
            await asyncio.sleep(0)

    ws_rpc._rx_task = asyncio.create_task(_rx_msgs())
    await asyncio.sleep(0)

    disconnect_task = asyncio.create_task(ws_rpc.disconnect())
    await rx_task_cancelled.wait()
    disconnect_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await disconnect_task


@pytest.mark.asyncio
async def test_disconnect_completes_when_called_from_cancelled_task(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test disconnect closes the client when called from a cancelled task."""

    async def _rx_msgs() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)

    async def _run() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # Cleanup inside a cancelled task: the rx task's CancelledError
            # must not be mistaken for a new cancellation of this task.
            ws_rpc._rx_task = asyncio.create_task(_rx_msgs())
            await asyncio.sleep(0)
            await ws_rpc.disconnect()
            raise

    task = asyncio.create_task(_run())
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert ws_rpc._rx_task is None
    ws_rpc._client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_wscall_timeout_without_auth_raises_device_connection_timeout_error(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test websocket call timeout raises DeviceConnectionTimeoutError without auth."""
    with (
        patch.object(ws_rpc, "_send_next_response", new=AsyncMock(return_value=None)),
        pytest.raises(DeviceConnectionTimeoutError),
    ):
        await ws_rpc.calls([("Shelly.GetConfig", None)], timeout=0.01)


@pytest.mark.asyncio
async def test_wscall_timeout_with_auth_raises_device_connection_timeout_error(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test websocket call timeout raises DeviceConnectionTimeoutError with auth."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    with (
        patch.object(ws_rpc, "_send_next_response", new=AsyncMock(return_value=None)),
        pytest.raises(DeviceConnectionTimeoutError),
    ):
        await ws_rpc.calls([("Shelly.GetConfig", None)], timeout=0.01)


@pytest.mark.asyncio
async def test_wscall_debug_logs_result_without_auth(
    ws_rpc: WsRPCMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test non-auth call path logs result details at debug level."""
    config_response = await load_device_fixture("shellyplugus", "Shelly.GetConfig")

    with caplog.at_level(logging.DEBUG, logger="aioshelly.rpc_device.wsrpc"):
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [config_response]
        )

    assert (
        f"result(127.0.0.1:80): Shelly.GetConfig(None) -> {config_response['result']}"
    ) in caplog.text


@pytest.mark.asyncio
async def test_wscall_debug_logs_result_with_auth(
    ws_rpc: WsRPCMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test auth call path logs result details at debug level."""
    config_response = await load_device_fixture("shellyplugus", "Shelly.GetConfig")
    ws_rpc.set_auth_data("auth_domain", "username", "password")

    with caplog.at_level(logging.DEBUG, logger="aioshelly.rpc_device.wsrpc"):
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [config_response]
        )

    assert (
        f"result(127.0.0.1:80): Shelly.GetConfig(None) -> {config_response['result']}"
    ) in caplog.text


@pytest.mark.asyncio
async def test_stale_true_triggers_retry_and_succeeds(ws_rpc: WsRPCMocker) -> None:
    """Test stale=true triggers retry with new nonce and succeeds."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    stale_challenge = make_401_response("nonce_value", True, 1)
    success = make_success_response({"ok": True})

    results = await ws_rpc.calls_with_mocked_responses(
        [("Cover.Close", {"id": 0})], [stale_challenge, success]
    )

    assert results[0] == {"ok": True}
    # Verify nonce and nc were updated (nc incremented after get_auth)
    assert ws_rpc._session.auth_data is not None
    assert ws_rpc._session.auth_data.nonce == "nonce_value"
    assert ws_rpc._session.auth_data.nc == 2


@pytest.mark.asyncio
async def test_double_stale_raises_invalid_auth(ws_rpc: WsRPCMocker) -> None:
    """Test double stale true raises InvalidAuthError (guard)."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    first = make_401_response("nonce_value", True, 1)
    second = make_401_response("nonce_value", True, 1)

    with pytest.raises(InvalidAuthError):
        await ws_rpc.calls_with_mocked_responses(
            [("Cover.Close", {"id": 0})], [first, second]
        )


@pytest.mark.asyncio
async def test_rpc_call_non401_error_raises_rpc_call_error(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test non-401 error response raises RpcCallError."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    bad_response = {
        "src": "shellyplus2pm-aabbccddeeff",
        "error": {"code": 404, "message": "Not Found"},
    }

    with pytest.raises(RpcCallError, match="Not Found"):
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [bad_response]
        )


@pytest.mark.asyncio
async def test_rpc_call_double_nonstale_401_raises_invalid_auth(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test two consecutive non-stale 401 responses raise InvalidAuthError."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    first = make_401_response("nonce1", stale=False, nc=1)
    second = make_401_response("nonce2", stale=False, nc=1)

    with pytest.raises(InvalidAuthError):
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [first, second]
        )


@pytest.mark.asyncio
async def test_rpc_call_invalid_json_401(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test 401 with invalid JSON raises InvalidAuthError."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    bad_401 = {
        "src": "shellyplus2pm-aabbccddeeff",
        "error": {"code": 401, "message": "lorem-ipsum"},
    }

    with pytest.raises(InvalidAuthError, match="lorem-ipsum"):
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [bad_401]
        )


AUTH_DATA = AuthData("auth_domain", "username", "password")
POLL_CALLS: list[tuple[str, dict[str, Any] | None]] = [
    ("Shelly.GetStatus", None),
    ("Shelly.GetComponents", {"dynamic_only": True}),
]


def _mock_send_until_pending(
    ws_rpc: WsRPCMocker, count: int
) -> tuple[AsyncMock, asyncio.Event]:
    """Mock away responses and signal once the given number of calls are pending."""
    pending = asyncio.Event()

    async def send_next_response() -> None:
        if len(ws_rpc._calls) >= count:
            pending.set()

    return AsyncMock(side_effect=send_next_response), pending


@pytest.mark.asyncio
async def test_wscall_connection_closed_no_unretrieved_exceptions(
    ws_rpc: WsRPCMocker, rpc_websocket_responses: ResponseMocker
) -> None:
    """Test connection closed during batched calls leaves no unretrieved futures."""
    loop = asyncio.get_running_loop()
    exception_handler = MagicMock()
    loop.set_exception_handler(exception_handler)

    send_next_response, pending = _mock_send_until_pending(ws_rpc, len(POLL_CALLS))
    with patch.object(ws_rpc, "_send_next_response", new=send_next_response):
        task = asyncio.create_task(ws_rpc.calls(POLL_CALLS))
        await pending.wait()
        await rpc_websocket_responses.mock_ws_message(
            WSMessage(WSMsgType.CLOSE, None, None)
        )
        with pytest.raises(DeviceConnectionError) as exc_info:
            await task

    assert ws_rpc._calls == {}

    # Release every reference to the abandoned futures so they get collected
    del task, exc_info
    await asyncio.sleep(0)
    gc.collect()
    loop.set_exception_handler(None)
    exception_handler.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_data", "calls", "send_frame_side_effect"),
    [
        pytest.param(
            None,
            POLL_CALLS,
            [None, ClientConnectionResetError("Cannot write to closing transport")],
            id="without_auth",
        ),
        pytest.param(
            AUTH_DATA,
            POLL_CALLS[:1],
            [ClientConnectionResetError("Cannot write to closing transport")],
            id="with_auth",
        ),
    ],
)
async def test_wscall_send_failure_drops_pending_calls(
    ws_rpc: WsRPCMocker,
    auth_data: AuthData | None,
    calls: list[tuple[str, dict[str, Any] | None]],
    send_frame_side_effect: list[Exception | None],
) -> None:
    """Test a failed send does not leave calls waiting for a response."""
    ws_rpc._session.auth_data = auth_data
    ws_rpc._client.send_frame.side_effect = send_frame_side_effect

    with (
        patch.object(ws_rpc, "_send_next_response", new=AsyncMock()),
        pytest.raises(ClientConnectionResetError),
    ):
        await ws_rpc.calls(calls)

    assert ws_rpc._calls == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_data", "pending_calls"),
    [
        pytest.param(None, len(POLL_CALLS), id="without_auth"),
        pytest.param(AUTH_DATA, 1, id="with_auth"),
    ],
)
async def test_wscall_cancelled_drops_pending_calls(
    ws_rpc: WsRPCMocker, auth_data: AuthData | None, pending_calls: int
) -> None:
    """Test cancelling the caller does not leave calls waiting for a response."""
    ws_rpc._session.auth_data = auth_data

    send_next_response, pending = _mock_send_until_pending(ws_rpc, pending_calls)
    with patch.object(ws_rpc, "_send_next_response", new=send_next_response):
        task = asyncio.create_task(ws_rpc.calls(POLL_CALLS))
        await pending.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert ws_rpc._calls == {}


@pytest.mark.asyncio
async def test_rx_msgs_invalid_message_is_logged_and_skipped(
    ws_rpc: WsRPCMocker,
    rpc_websocket_responses: ResponseMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an invalid message is logged, not re-dispatched, and rx keeps running."""
    received: list[str] = []
    second_received = asyncio.Event()

    def on_notification(_: RPCSource, method: str, __: dict | None) -> None:
        received.append(method)
        if method == "NotifySecond":
            second_received.set()

    async def send_notification(method: str) -> None:
        frame = {"src": "shellyplus2pm-aabbccddeeff", "method": method}
        await rpc_websocket_responses.mock_ws_message(
            WSMessage(WSMsgType.TEXT, json_bytes(frame), None)
        )

    with (
        patch.object(ws_rpc, "_on_notification", side_effect=on_notification),
        caplog.at_level(logging.ERROR, logger="aioshelly.rpc_device.wsrpc"),
    ):
        await send_notification("NotifyFirst")
        await rpc_websocket_responses.mock_ws_message(
            WSMessage(WSMsgType.BINARY, b"binary", None)
        )
        await send_notification("NotifySecond")
        async with asyncio.timeout(1):
            await second_received.wait()

    assert (
        "Invalid Message from host 127.0.0.1:80: Received non-Text message"
        in caplog.text
    )
    # The invalid message must not re-dispatch the previous frame
    assert received == ["NotifyFirst", "NotifySecond"]
    assert ws_rpc.connected
    assert not ws_rpc._rx_task.done()


@pytest.mark.asyncio
async def test_rx_msgs_invalid_first_message_keeps_rx_running(
    ws_rpc: WsRPCMocker,
    rpc_websocket_responses: ResponseMocker,
) -> None:
    """Test an invalid message before any frame was received does not kill rx."""
    received: list[str] = []
    notified = asyncio.Event()

    def on_notification(_: RPCSource, method: str, __: dict | None) -> None:
        received.append(method)
        notified.set()

    with patch.object(ws_rpc, "_on_notification", side_effect=on_notification):
        await rpc_websocket_responses.mock_ws_message(
            WSMessage(WSMsgType.BINARY, b"binary", None)
        )
        frame = {"src": "shellyplus2pm-aabbccddeeff", "method": "NotifyStatus"}
        await rpc_websocket_responses.mock_ws_message(
            WSMessage(WSMsgType.TEXT, json_bytes(frame), None)
        )
        async with asyncio.timeout(1):
            await notified.wait()

    assert received == ["NotifyStatus"]
    assert ws_rpc.connected
    assert not ws_rpc._rx_task.done()


def test_auth_data_update_challenge_accepts_string_nc() -> None:
    """Test challenge update coerces a string nc (Shelly WallDisplay) to int."""
    auth_data = AuthData("auth_domain", "username", "password")

    auth_data.update_challenge(
        {"nonce": "test_nonce", "algorithm": "SHA-256", "nc": "5"}
    )

    assert auth_data.nonce == "test_nonce"
    assert auth_data.nc == 5


def test_auth_data_update_challenge_defaults_nc_to_one() -> None:
    """Test challenge update uses nc=1 when the challenge has no nc."""
    auth_data = AuthData("auth_domain", "username", "password")

    auth_data.update_challenge({"nonce": "test_nonce", "algorithm": "SHA-256"})

    assert auth_data.nc == 1


def test_auth_data_get_auth_builds_digest_and_increments_nc() -> None:
    """Test get_auth returns a valid digest frame and increments nc."""
    auth_data = AuthData("auth_domain", "username", "password")
    auth_data.update_challenge({"nonce": "test_nonce", "algorithm": "SHA-256", "nc": 3})

    frame = auth_data.get_auth()

    assert auth_data.ha1 == hex_hash("username:auth_domain:password")
    assert frame["realm"] == "auth_domain"
    assert frame["username"] == "username"
    assert frame["nonce"] == "test_nonce"
    assert frame["nc"] == 3
    assert frame["algorithm"] == "SHA-256"
    assert frame["response"] == hex_hash(
        f"{auth_data.ha1}:test_nonce:3:{frame['cnonce']}:auth:{HA2}"
    )
    assert auth_data.nc == 4


def _make_rpc_call(
    params: dict[str, Any] | None = None,
    session: SessionData | None = None,
) -> RPCCall:
    """Build an RPCCall with a fresh future."""
    if session is None:
        session = SessionData("aios-1", None, None)
    return RPCCall(
        7,
        "Shelly.GetStatus",
        params,
        session,
        asyncio.get_running_loop().create_future(),
    )


@pytest.mark.asyncio
async def test_rpc_call_repr() -> None:
    """Test RPCCall representation."""
    call = _make_rpc_call({"id": 0})
    call.result = {"ok": True}

    assert repr(call) == (
        "<RPCCall method=Shelly.GetStatus params={'id': 0} "
        "call_id=7 result={'ok': True}>"
    )


@pytest.mark.asyncio
async def test_rpc_call_build_request_frame_minimal() -> None:
    """Test request frame omits params, dst and auth when not available."""
    call = _make_rpc_call()

    assert call.build_request_frame() == {
        "id": 7,
        "method": "Shelly.GetStatus",
        "src": "aios-1",
    }


@pytest.mark.asyncio
async def test_rpc_call_build_request_frame_full() -> None:
    """Test request frame includes params, dst and auth once a nonce is known."""
    auth_data = AuthData("auth_domain", "username", "password")
    session = SessionData("aios-1", "shellyplus2pm-aabbccddeeff", auth_data)
    call = _make_rpc_call({"id": 0}, session)

    # No nonce yet: auth must not be added
    assert "auth" not in call.build_request_frame()

    auth_data.update_challenge({"nonce": "test_nonce", "algorithm": "SHA-256"})
    frame = call.build_request_frame()

    assert frame["params"] == {"id": 0}
    assert frame["dst"] == "shellyplus2pm-aabbccddeeff"
    assert frame["auth"]["nonce"] == "test_nonce"


@pytest.mark.asyncio
async def test_connect_when_already_connected_raises(
    ws_rpc: WsRPCMocker, client_session: ClientSession
) -> None:
    """Test connecting an already connected client raises RuntimeError."""
    with pytest.raises(RuntimeError, match="Already connected"):
        await ws_rpc.connect(client_session)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ClientError("connection refused"),
        WSServerHandshakeError(MagicMock(), (), status=400, message="bad handshake"),
    ],
)
async def test_connect_client_error_raises_device_connection_error(
    ws_rpc: WsRPCMocker, client_session: ClientSession, error: Exception
) -> None:
    """Test aiohttp client errors during connect raise DeviceConnectionError."""
    await ws_rpc.disconnect()
    client_session.ws_connect.side_effect = error

    with pytest.raises(DeviceConnectionError):
        await ws_rpc.connect(client_session)

    assert not ws_rpc.connected


@pytest.mark.asyncio
async def test_connect_setsockopt_failure_logs_warning(
    ws_rpc: WsRPCMocker,
    client_session: ClientSession,
    rpc_websocket_response: ClientWebSocketResponse,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failing to set the socket receive buffer size is only logged."""
    await ws_rpc.disconnect()
    sock = rpc_websocket_response.get_extra_info.return_value
    sock.setsockopt.side_effect = OSError("not supported")

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await ws_rpc.connect(client_session)

    assert ws_rpc.connected
    assert (
        "127.0.0.1:80: Failed to set socket receive buffer size: not supported"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_handle_frame_method_call_replies_not_implemented(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test a peer method call with an id gets a 'Not Implemented' error reply."""
    frame = {"id": 42, "src": "shellyplus2pm-aabbccddeeff", "method": "Shelly.Foo"}

    with patch.object(ws_rpc, "_send_next_response", new=AsyncMock()):
        ws_rpc.handle_frame(RPCSource.CLIENT, frame)
        assert len(ws_rpc._background_tasks) == 1
        await asyncio.gather(*ws_rpc._background_tasks)

    assert ws_rpc._background_tasks == set()
    ws_rpc._client.send_frame.assert_awaited_once_with(
        json_bytes(
            {
                "id": 42,
                "src": ws_rpc._session.src,
                "error": {"code": 500, "message": "Not Implemented"},
            }
        ),
        WSMsgType.TEXT,
    )


@pytest.mark.asyncio
async def test_handle_frame_notification_calls_on_notification(
    ws_rpc: WsRPCMocker, notify_history: NotifyHistory
) -> None:
    """Test a method frame without id is dispatched as a notification."""
    params = {"ts": 1.0, "switch:0": {"output": True}}
    frame = {
        "src": "shellyplus2pm-aabbccddeeff",
        "method": "NotifyStatus",
        "params": params,
    }

    ws_rpc.handle_frame(RPCSource.CLIENT, frame)

    assert notify_history.history == [(RPCSource.CLIENT, "NotifyStatus", params)]
    assert ws_rpc._session.dst == "shellyplus2pm-aabbccddeeff"


@pytest.mark.asyncio
async def test_handle_frame_notification_handler_error_is_logged(
    ws_rpc: WsRPCMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an exception raised by the notification callback is logged."""
    frame = {"src": "shellyplus2pm-aabbccddeeff", "method": "NotifyEvent"}

    with (
        patch.object(ws_rpc, "_on_notification", side_effect=ValueError("boom")),
        caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
    ):
        ws_rpc.handle_frame(RPCSource.CLIENT, frame)

    assert f"Error handling notification frame: {frame}" in caplog.text
    assert "ValueError: boom" in caplog.text


@pytest.mark.asyncio
async def test_handle_frame_logs_warning_when_remote_src_changes(
    ws_rpc: WsRPCMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a changed peer src is logged and the session dst is updated."""
    ws_rpc.handle_frame(RPCSource.CLIENT, {"src": "device-1", "method": "Notify"})

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        ws_rpc.handle_frame(RPCSource.CLIENT, {"src": "device-2", "method": "Notify"})

    assert "Remote src changed: device-1 -> device-2" in caplog.text
    assert ws_rpc._session.dst == "device-2"


@pytest.mark.asyncio
async def test_handle_frame_unknown_response_id_logs_warning(
    ws_rpc: WsRPCMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a response for an unknown request id is logged and dropped."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        ws_rpc.handle_frame(
            RPCSource.CLIENT,
            {"id": 999, "src": "shellyplus2pm-aabbccddeeff", "result": {}},
        )

    assert (
        "Response from (127.0.0.1:80) for an unknown request id: 999: None"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_handle_frame_response_for_cancelled_call_is_dropped(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test a response for a cancelled call does not set a result on the future."""
    call = _make_rpc_call()
    call.resolve.cancel()
    ws_rpc._calls[call.call_id] = call

    ws_rpc.handle_frame(RPCSource.CLIENT, {"id": call.call_id, "result": {}})

    assert ws_rpc._calls == {}
    assert call.resolve.cancelled()


@pytest.mark.asyncio
async def test_handle_frame_invalid_frame_logs_warning(
    ws_rpc: WsRPCMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a frame without method and id is logged as invalid."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        ws_rpc.handle_frame(RPCSource.CLIENT, {"src": "shellyplus2pm-aabbccddeeff"})

    assert "Invalid frame: {'src': 'shellyplus2pm-aabbccddeeff'}" in caplog.text


async def _send_notification(
    rpc_websocket_responses: ResponseMocker, method: str
) -> None:
    """Push a notification frame into the mocked websocket."""
    frame = {"src": "shellyplus2pm-aabbccddeeff", "method": method}
    await rpc_websocket_responses.mock_ws_message(
        WSMessage(WSMsgType.TEXT, json_bytes(frame), None)
    )


@pytest.mark.asyncio
async def test_rx_msgs_unexpected_error_is_logged_and_reraised(
    ws_rpc: WsRPCMocker,
    rpc_websocket_responses: ResponseMocker,
    notify_history: NotifyHistory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected receive error is logged, closes the connection and raises."""
    rx_task = ws_rpc._rx_task
    # The rx task is awaiting the current receive; the next one will fail
    ws_rpc._client.receive = AsyncMock(side_effect=RuntimeError("unexpected"))
    await _send_notification(rpc_websocket_responses, "NotifyStatus")

    with (
        caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
        pytest.raises(RuntimeError, match="unexpected"),
    ):
        await rx_task

    assert "Unexpected error while receiving message" in caplog.text
    assert notify_history.history[-1] == (RPCSource.CLIENT, NOTIFY_WS_CLOSED, None)
    assert not ws_rpc.connected
    # The failed task has already been awaited, keep disconnect() from re-raising
    ws_rpc._rx_task = None


@pytest.mark.asyncio
async def test_rx_msgs_stops_when_client_closed_after_receive(
    ws_rpc: WsRPCMocker,
    rpc_websocket_responses: ResponseMocker,
    notify_history: NotifyHistory,
) -> None:
    """Test the rx loop ends without dispatching when the client closed meanwhile."""
    client = ws_rpc._client
    client.closed = True
    await _send_notification(rpc_websocket_responses, "NotifyStatus")

    await ws_rpc._rx_task

    assert notify_history.history == [(RPCSource.CLIENT, NOTIFY_WS_CLOSED, None)]
    assert not ws_rpc.connected
    client.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_rx_msgs_closed_fails_only_pending_calls(
    ws_rpc: WsRPCMocker, rpc_websocket_responses: ResponseMocker
) -> None:
    """Test closing the connection fails pending calls and keeps resolved ones."""
    loop = asyncio.get_running_loop()
    session = SessionData("aios-1", None, None)
    resolved = RPCCall(1, "Shelly.GetStatus", None, session, loop.create_future())
    resolved.resolve.set_result({"id": 1, "result": {}})
    pending = RPCCall(2, "Shelly.GetConfig", None, session, loop.create_future())
    ws_rpc._calls = {resolved.call_id: resolved, pending.call_id: pending}

    await rpc_websocket_responses.mock_ws_message(
        WSMessage(WSMsgType.CLOSE, None, None)
    )
    await ws_rpc._rx_task

    assert ws_rpc._calls == {}
    assert resolved.resolve.result() == {"id": 1, "result": {}}
    with pytest.raises(DeviceConnectionError):
        pending.resolve.result()


@pytest.mark.asyncio
async def test_call_returns_single_result(ws_rpc: WsRPCMocker) -> None:
    """Test call() returns the result of a single RPC call."""
    ws_rpc.next_id_mock = ws_rpc._call_id
    ws_rpc.responses = [make_success_response({"ok": True})]

    assert await ws_rpc.call("Shelly.GetStatus") == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth_data", [None, AUTH_DATA], ids=["without_auth", "with_auth"]
)
@pytest.mark.parametrize(
    "response",
    [
        {"src": "shellyplus2pm-aabbccddeeff"},
        {"src": "shellyplus2pm-aabbccddeeff", "error": {"code": 500}},
    ],
    ids=["no_error", "no_message"],
)
async def test_wscall_malformed_error_response_raises_rpc_call_error(
    ws_rpc: WsRPCMocker, auth_data: AuthData | None, response: dict[str, Any]
) -> None:
    """Test a response without result and without a valid error raises."""
    ws_rpc._session.auth_data = auth_data

    with pytest.raises(RpcCallError, match="bad response") as exc_info:
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [response]
        )

    assert exc_info.value.code == 0


@pytest.mark.asyncio
async def test_wscalls_non401_error_without_auth_raises_rpc_call_error(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test a non-401 error on the batched (non-auth) path raises RpcCallError."""
    response = {
        "src": "shellyplus2pm-aabbccddeeff",
        "error": {"code": 404, "message": "Not Found"},
    }

    with pytest.raises(RpcCallError, match="Not Found") as exc_info:
        await ws_rpc.calls_with_mocked_responses(
            [("Shelly.GetConfig", None)], [response]
        )

    assert exc_info.value.code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_data", "allow_auth_retry", "expected"),
    [
        pytest.param(AUTH_DATA, True, None, id="retry_allowed"),
        pytest.param(AUTH_DATA, False, InvalidAuthError, id="retry_not_allowed"),
        pytest.param(None, True, InvalidAuthError, id="no_auth_data"),
    ],
)
async def test_raise_for_unrecoverable_errors_401(
    ws_rpc: WsRPCMocker,
    auth_data: AuthData | None,
    allow_auth_retry: bool,
    expected: type[Exception] | None,
) -> None:
    """Test 401 handling in _raise_for_unrecoverable_errors."""
    ws_rpc._session.auth_data = auth_data

    if expected is None:
        assert (
            ws_rpc._raise_for_unrecoverable_errors(
                401, "unauthorized", allow_auth_retry
            )
            is None
        )
        return

    with pytest.raises(expected, match="unauthorized"):
        ws_rpc._raise_for_unrecoverable_errors(401, "unauthorized", allow_auth_retry)


def test_ws_server_subscribe_updates_returns_unsubscribe() -> None:
    """Test subscribing returns a callable that removes the subscription."""
    ws_server = WsServer()
    callback = MagicMock()

    unsubscribe = ws_server.subscribe_updates("AABBCCDDEEFF", callback)

    assert ws_server.subscriptions == {"AABBCCDDEEFF": callback}
    unsubscribe()
    assert ws_server.subscriptions == {}


@pytest.mark.asyncio
async def test_ws_server_close_without_initialize_is_noop() -> None:
    """Test closing a server that was never initialized does nothing."""
    ws_server = WsServer()

    ws_server.close()

    assert ws_server._background_tasks == set()


@pytest.mark.asyncio
async def test_ws_server_initialize_and_close() -> None:
    """Test initialize sets up the app runner and close schedules its cleanup."""
    ws_server = WsServer()

    with (
        patch("aioshelly.rpc_device.wsrpc.AppRunner") as runner_cls,
        patch("aioshelly.rpc_device.wsrpc.TCPSite") as site_cls,
    ):
        runner = runner_cls.return_value
        runner.setup = AsyncMock()
        runner.cleanup = AsyncMock()
        site = site_cls.return_value
        site.start = AsyncMock()

        await ws_server.initialize(8123, "/custom/ws")

        app = runner_cls.call_args.args[0]
        assert isinstance(app, Application)
        assert {(r.method, r.resource.canonical) for r in app.router.routes()} == {
            ("GET", "/custom/ws"),
            ("HEAD", "/custom/ws"),
        }
        runner.setup.assert_awaited_once()
        site_cls.assert_called_once_with(runner, port=8123)
        site.start.assert_awaited_once()

        ws_server.close()
        assert len(ws_server._background_tasks) == 1
        await asyncio.gather(*ws_server._background_tasks)

    runner.cleanup.assert_awaited_once()
    assert ws_server._background_tasks == set()


@pytest.mark.asyncio
async def test_ws_server_websocket_handler_dispatches_frames(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the websocket handler routes frames to device id or host subscribers."""
    ws_server = WsServer()
    device_frames: list[dict[str, Any]] = []
    host_frames: list[dict[str, Any]] = []
    received = asyncio.Event()

    def on_device_frame(frame: dict[str, Any]) -> None:
        device_frames.append(frame)
        received.set()

    def on_host_frame(frame: dict[str, Any]) -> None:
        host_frames.append(frame)
        received.set()

    async def send_and_wait(ws: ClientWebSocketResponse, payload: str) -> None:
        received.clear()
        await ws.send_str(payload)
        async with asyncio.timeout(1):
            await received.wait()

    ws_server.subscribe_updates("AABBCCDDEEFF", on_device_frame)
    unsubscribe_host = ws_server.subscribe_updates("127.0.0.1", on_host_frame)

    app = Application()
    app.add_routes([get(WS_API_URL, ws_server.websocket_handler)])
    device_frame = {"src": "shellyplus2pm-aabbccddeeff", "method": "NotifyStatus"}
    unknown_frame = {"src": "shellyplus1-001122334455", "method": "NotifyStatus"}

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        async with (
            TestClient(TestServer(app)) as client,
            client.ws_connect(WS_API_URL) as ws,
        ):
            # Frames that cannot be dispatched are logged and skipped
            await ws.send_str("not-json")
            await ws.send_str(json_dumps({"method": "NotifyStatus"}))
            await ws.send_str(json_dumps({"src": "nodash"}))
            # Known device id goes to the device subscriber
            await send_and_wait(ws, json_dumps(device_frame))
            # Unknown device id falls back to the host subscriber
            await send_and_wait(ws, json_dumps(unknown_frame))
            # Without a host subscriber the frame is dropped
            unsubscribe_host()
            await ws.send_str(json_dumps(unknown_frame))
            await send_and_wait(ws, json_dumps(device_frame))

    assert device_frames == [device_frame, device_frame]
    assert host_frames == [unknown_frame]
    assert "Websocket server connection from 127.0.0.1 ready" in caplog.text
    assert "Invalid Message from host 127.0.0.1: Received invalid JSON" in caplog.text
    assert "Invalid device id from host 127.0.0.1: 'src'" in caplog.text
    assert "Invalid device id from host 127.0.0.1: list index out of range" in (
        caplog.text
    )
    assert "Calling WsRPC message update for device id AABBCCDDEEFF" in caplog.text
    assert "Calling WsRPC message update for host 127.0.0.1" in caplog.text
    assert "Websocket server connection from 127.0.0.1 closed" in caplog.text


@pytest.mark.asyncio
async def test_ws_server_websocket_handler_closes_on_close_frame() -> None:
    """Test a close frame surfaced by the websocket response closes it."""
    ws_server = WsServer()
    request = MagicMock(remote="127.0.0.1")

    with patch("aioshelly.rpc_device.wsrpc.WebSocketResponse") as ws_res_cls:
        ws_res = ws_res_cls.return_value
        ws_res.prepare = AsyncMock()
        ws_res.close = AsyncMock()
        ws_res.__aiter__.return_value = [WSMessage(WSMsgType.CLOSE, None, None)]

        result = await ws_server.websocket_handler(request)

    assert result is ws_res
    ws_res_cls.assert_called_once_with(protocols=["json-rpc"])
    ws_res.prepare.assert_awaited_once_with(request)
    ws_res.close.assert_awaited_once()
