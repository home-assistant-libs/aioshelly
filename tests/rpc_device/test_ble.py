"""Tests for BLE module."""

from typing import Any

import pytest

from aioshelly.ble import async_ble_supported
from aioshelly.exceptions import RpcCallError
from aioshelly.rpc_device.device import RpcDevice


@pytest.mark.parametrize(
    ("side_effect", "ble_supported"),
    [
        (RpcCallError(-105, "Argument 'id', value 1 not found!"), True),
        (RpcCallError(-114, "Method Script.GetCode failed: Method not found!"), False),
        (RpcCallError(404, "No handler for Script.GetCode"), False),
        (
            [
                {
                    "id": 5,
                    "src": "shellyplus2pm-a8032ab720ac",
                    "dst": "aios-2293750469632",
                    "result": {"data": "script"},
                }
            ],
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_async_ble_supported(
    rpc_device: RpcDevice,
    side_effect: Exception | dict[str, Any],
    ble_supported: bool,
) -> None:
    """Test async_ble_supported method."""
    rpc_device.call_rpc_multiple.side_effect = [side_effect]

    result = await async_ble_supported(rpc_device)

    assert result == ble_supported
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.GetCode"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"id": 1}


@pytest.mark.asyncio
async def test_async_ble_supported_raises_unkown_errors(rpc_device: RpcDevice) -> None:
    """Test async_ble_supported raises for unknown errors."""
    message = "Missing required argument 'id'!"
    rpc_device.call_rpc_multiple.side_effect = [RpcCallError(-103, message)]

    with pytest.raises(RpcCallError, match=message):
        await async_ble_supported(rpc_device)
