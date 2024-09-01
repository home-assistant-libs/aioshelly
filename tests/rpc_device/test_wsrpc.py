"""Tests for rpc_device.device module."""

import pytest

from . import load_device_fixture
from .conftest import WsRPCMocker


@pytest.mark.asyncio
async def test_device_wscall(ws_rpc: WsRPCMocker) -> None:
    """Test wscall."""
    config_response = await load_device_fixture("shellyplugus", "Shelly.GetConfig")
    calls = [("Shelly.GetConfig", None)]
    responses = [config_response]
    await ws_rpc.calls_with_mocked_responses(calls, responses)
