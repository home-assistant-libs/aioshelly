"""Tests for the BLE initialization."""

from __future__ import annotations

from unittest.mock import MagicMock

import habluetooth
import pytest
import pytest_asyncio
from habluetooth import BluetoothScanningMode

from aioshelly.ble import create_scanner


@pytest_asyncio.fixture(autouse=True)
async def ha_manager() -> MagicMock:
    """Mock ha manager."""
    await habluetooth.BluetoothManager().async_setup()


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
