"""Tests for rpc_device.wsrpc module."""

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp.http_websocket import WSMessage, WSMsgType

from aioshelly.exceptions import (
    ConnectionClosed,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    InvalidMessage,
)
from aioshelly.rpc_device.wsrpc import AuthData, _receive_json_or_raise

from . import load_device_fixture
from .conftest import WsRPCMocker


def test_receive_json_or_raise_text_returns_decoded_json() -> None:
    """Test text message with JSON payload returns decoded dict."""
    msg = WSMessage(WSMsgType.TEXT, '{"key":"value","n":1}', None)

    assert _receive_json_or_raise(msg) == {"key": "value", "n": 1}


def test_receive_json_or_raise_text_invalid_json_raises_invalid_message() -> None:
    """Test text message with invalid JSON raises InvalidMessage."""
    msg = WSMessage(WSMsgType.TEXT, "not-json", None)

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
async def test_wscall_timeout_with_auth_reraises_cancelled_error(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test timeout cleanup re-raises CancelledError when current task is cancelled."""
    ws_rpc.set_auth_data("auth_domain", "username", "password")
    with (
        patch.object(ws_rpc, "_send_next_response", new=AsyncMock(return_value=None)),
        patch("aioshelly.rpc_device.wsrpc._current_task_cancelled", return_value=True),
        pytest.raises(asyncio.CancelledError),
    ):
        await ws_rpc.calls([("Shelly.GetConfig", None)], timeout=0.01)


@pytest.mark.asyncio
async def test_wscall_timeout_without_auth_reraises_cancelled_error(
    ws_rpc: WsRPCMocker,
) -> None:
    """Test timeout cleanup re-raises CancelledError when current task is cancelled."""
    with (
        patch.object(ws_rpc, "_send_next_response", new=AsyncMock(return_value=None)),
        patch("aioshelly.rpc_device.wsrpc._current_task_cancelled", return_value=True),
        pytest.raises(asyncio.CancelledError),
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
