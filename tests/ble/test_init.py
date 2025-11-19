"""Tests for the BLE initialization."""

from __future__ import annotations

import pytest
from habluetooth import BluetoothScanningMode

from aioshelly.ble import (
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
