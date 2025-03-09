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
async def test_create_scanner() -> None:
    """Test create scanner."""
    scanner = create_scanner(
        "AA:BB:CC:DD:EE:FF",
        "shelly",
        BluetoothScanningMode.ACTIVE,
        BluetoothScanningMode.ACTIVE,
    )
    assert scanner.requested_mode == BluetoothScanningMode.ACTIVE
    assert scanner.current_mode == BluetoothScanningMode.ACTIVE
