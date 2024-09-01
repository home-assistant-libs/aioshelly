"""Tests for rpc_device.wsrpc module."""

import pytest

from aioshelly.exceptions import InvalidAuthError

from . import load_device_fixture
from .conftest import WsRPCMocker


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
    responses = [cover_close_auth_fail, cover_close_success]
    results = await ws_rpc_with_auth.calls_with_mocked_responses(calls, responses)
    assert results[0] == cover_close_success["result"]
