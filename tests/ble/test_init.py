"""Tests for the BLE initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from habluetooth import BluetoothScanningMode

from aioshelly.ble import (
    async_ensure_ble_enabled,
    create_scanner,
    get_device_from_model_id,
    get_name_from_model_id,
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


@pytest.mark.asyncio
async def test_async_ensure_ble_enabled_already_enabled(
    mock_rpc_device: AsyncMock,
) -> None:
    """Test async_ensure_ble_enabled method when BLE is already enabled."""
    mock_rpc_device.ble_getconfig.return_value = {
        "enable": True,
        "rpc": {"enable": False},
    }

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
