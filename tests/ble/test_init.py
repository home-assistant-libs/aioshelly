"""Tests for the BLE initialization."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, call

import pytest
from habluetooth import BluetoothScanningMode

from aioshelly.ble import (
    async_ensure_ble_enabled,
    async_get_ble_script_id,
    async_set_active_mode,
    create_scanner,
    get_device_from_model_id,
    get_name_from_model_id,
)
from aioshelly.ble.const import (
    BLE_CODE,
    BLE_SCRIPT_NAME,
    VAR_ACTIVE,
    VAR_EVENT_TYPE,
    VAR_VERSION,
)
from aioshelly.const import DEVICES
from aioshelly.exceptions import RpcCallError


def _build_ble_script_code(active: bool, event_type: str, data_version: int) -> str:
    """Build the expected BLE script code for a given configuration."""
    return (
        BLE_CODE.replace(VAR_ACTIVE, "true" if active else "false")
        .replace(VAR_EVENT_TYPE, event_type)
        .replace(VAR_VERSION, str(data_version))
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested_mode", "current_mode"),
    [
        (BluetoothScanningMode.ACTIVE, BluetoothScanningMode.ACTIVE),
        (BluetoothScanningMode.PASSIVE, BluetoothScanningMode.PASSIVE),
        (BluetoothScanningMode.ACTIVE, BluetoothScanningMode.PASSIVE),
        (BluetoothScanningMode.PASSIVE, BluetoothScanningMode.ACTIVE),
    ],
)
async def test_create_scanner(
    requested_mode: BluetoothScanningMode, current_mode: BluetoothScanningMode
) -> None:
    """Test create scanner."""
    scanner = create_scanner(
        "AA:BB:CC:DD:EE:FF", "shelly", requested_mode, current_mode
    )
    assert scanner.requested_mode == requested_mode
    assert scanner.current_mode == current_mode


@pytest.mark.parametrize(
    "ble_config",
    [
        {
            "enable": True,
            "rpc": {"enable": False},
        },
        {"rpc": {"enable": False}},  # for fw 2.0.0+ where "enable" is removed
    ],
)
@pytest.mark.asyncio
async def test_async_ensure_ble_enabled_already_enabled(
    mock_rpc_device: AsyncMock,
    ble_config: dict[str, Any],
) -> None:
    """Test async_ensure_ble_enabled method when BLE is already enabled."""
    mock_rpc_device.ble_getconfig.return_value = ble_config

    result = await async_ensure_ble_enabled(mock_rpc_device)
    assert result is False
    mock_rpc_device.ble_getconfig.assert_called_once()
    mock_rpc_device.ble_setconfig.assert_not_called()
    mock_rpc_device.trigger_reboot.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("restart_required", [True, False])
async def test_async_ensure_ble_enabled_restart_required(
    mock_rpc_device: AsyncMock, restart_required: bool
) -> None:
    """Test async_ensure_ble_enabled method restart_required flag."""
    mock_rpc_device.ble_getconfig.return_value = {
        "enable": False,
        "rpc": {"enable": False},
    }
    mock_rpc_device.ble_setconfig.return_value = {"restart_required": restart_required}

    result = await async_ensure_ble_enabled(mock_rpc_device)
    assert result == restart_required
    mock_rpc_device.ble_getconfig.assert_called_once()
    mock_rpc_device.ble_setconfig.assert_called_once_with(enable=True, enable_rpc=False)
    assert mock_rpc_device.trigger_reboot.called == restart_required


@pytest.mark.asyncio
async def test_create_scanner_back_compat() -> None:
    """Test create scanner works without modes."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    assert scanner.requested_mode is None
    assert scanner.current_mode is None


def test_get_device_from_model_id() -> None:
    """Test get_device_from_model_id helper function."""
    # Test with valid model ID (Shelly 1 Mini Gen4)
    device = get_device_from_model_id(0x1030)
    assert device is not None
    assert device.name == "Shelly 1 Mini Gen4"
    assert device.model == "S4SW-001X8EU"

    # Test with another valid model ID (Shelly 2PM Gen3)
    device = get_device_from_model_id(0x1005)
    assert device is not None
    assert device.name == "Shelly 2PM Gen3"
    assert device.model == "S3SW-002P16EU"

    # Test with invalid model ID
    device = get_device_from_model_id(0x9999)
    assert device is None


def test_get_name_from_model_id() -> None:
    """Test get_name_from_model_id helper function."""
    # Test with valid model ID (Shelly 1PM Gen4)
    name = get_name_from_model_id(0x1029)
    assert name == "Shelly 1PM Gen4"

    # Test with another valid model ID (Shelly Flood Gen4)
    name = get_name_from_model_id(0x1822)
    assert name == "Shelly Flood Gen4"

    # Test with invalid model ID
    name = get_name_from_model_id(0x9999)
    assert name is None


@pytest.mark.asyncio
async def test_async_get_ble_script_id_found() -> None:
    """The integration script id is resolved by name."""
    device = AsyncMock()
    device.script_list = AsyncMock(
        return_value=[
            {"name": "other", "id": 1},
            {"name": "aioshelly_ble_integration", "id": 7},
        ]
    )
    assert await async_get_ble_script_id(device) == 7


@pytest.mark.asyncio
async def test_async_get_ble_script_id_missing() -> None:
    """If no integration script is installed the helper returns None."""
    device = AsyncMock()
    device.script_list = AsyncMock(return_value=[{"name": "other", "id": 1}])
    assert await async_get_ble_script_id(device) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("active", "expected_code"),
    [
        (True, "setActive(true)"),
        (False, "setActive(false)"),
    ],
)
async def test_async_set_active_mode(active: bool, expected_code: str) -> None:
    """Script.Eval is called with the right setActive expression."""
    device = AsyncMock()
    device.script_eval = AsyncMock()
    await async_set_active_mode(device, 7, active=active)
    device.script_eval.assert_awaited_once_with(7, expected_code)


def test_duplicate_model_ids() -> None:
    """Check for duplicate model IDs in DEVICES."""
    by_id = defaultdict(list)

    for model, device in DEVICES.items():
        if device.model_id is not None:
            by_id[device.model_id].append((model, device.name))

    duplicates = {
        f"{model_id:#04x}": entries
        for model_id, entries in by_id.items()
        if len(entries) > 1
    }

    assert not duplicates, "Duplicate model IDs found in DEVICES"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script_list_response", "expected_script_stop_calls"),
    [
        ([{"name": "other", "id": 1}, {"name": BLE_SCRIPT_NAME, "id": 2}], [call(2)]),
        ([{"name": "other", "id": 1}], []),
    ],
    ids=["script_present", "script_absent"],
)
async def test_async_stop_scanner(
    mock_rpc_device: AsyncMock,
    script_list_response: list[dict[str, int | str]],
    expected_script_stop_calls: list[Any],
) -> None:
    """Test stop scanner behavior with and without the integration script."""
    mock_rpc_device.script_list.return_value = script_list_response

    await async_stop_scanner(mock_rpc_device)

    assert mock_rpc_device.script_stop.call_args_list == expected_script_stop_calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "script_list_responses",
        "script_getcode_setup",
        "active",
        "event_type",
        "data_version",
        "expected_script_create_calls",
        "expected_script_stop_calls",
        "expected_script_putcode_calls",
        "expected_script_start_calls",
    ),
    [
        (
            [[{"name": "other", "id": 10}], [{"name": BLE_SCRIPT_NAME, "id": 42}]],
            lambda mock: setattr(
                mock.script_getcode,
                "side_effect",
                RpcCallError(-1, "no code"),
            ),
            True,
            "ble.scan_result",
            2,
            [call(BLE_SCRIPT_NAME)],
            [call(42)],
            [call(42, _build_ble_script_code(True, "ble.scan_result", 2))],
            [call(42)],
        ),
        (
            [[{"name": BLE_SCRIPT_NAME, "id": 7}]],
            lambda mock: setattr(
                mock.script_getcode,
                "return_value",
                {"data": "old code"},
            ),
            False,
            "custom.event",
            3,
            [],
            [call(7)],
            [call(7, _build_ble_script_code(False, "custom.event", 3))],
            [call(7)],
        ),
        (
            [[{"name": BLE_SCRIPT_NAME, "id": 9}]],
            lambda mock: setattr(
                mock.script_getcode,
                "return_value",
                {"data": _build_ble_script_code(True, "ble.scan_result", 2)},
            ),
            True,
            "ble.scan_result",
            2,
            [],
            [],
            [],
            [call(9)],
        ),
    ],
    ids=[
        "script_missing_create_and_update",
        "script_present_code_mismatch_update",
        "script_present_code_match_no_update",
    ],
)
async def test_async_start_scanner(
    mock_rpc_device: AsyncMock,
    script_list_responses: list[list[dict[str, int | str]]],
    script_getcode_setup: Any,
    active: bool,
    event_type: str,
    data_version: int,
    expected_script_create_calls: list[Any],
    expected_script_stop_calls: list[Any],
    expected_script_putcode_calls: list[Any],
    expected_script_start_calls: list[Any],
) -> None:
    """Test start scanner behavior across missing, changed, and matching scripts."""
    mock_rpc_device.script_list.side_effect = iter(script_list_responses)
    script_getcode_setup(mock_rpc_device)

    await async_start_scanner(
        mock_rpc_device,
        active=active,
        event_type=event_type,
        data_version=data_version,
    )

    assert mock_rpc_device.script_create.call_args_list == expected_script_create_calls
    assert mock_rpc_device.script_stop.call_args_list == expected_script_stop_calls
    assert (
        mock_rpc_device.script_putcode.call_args_list == expected_script_putcode_calls
    )
    assert mock_rpc_device.script_start.call_args_list == expected_script_start_calls
