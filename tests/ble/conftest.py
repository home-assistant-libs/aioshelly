"""Tests for the BLE."""

from __future__ import annotations

from unittest.mock import MagicMock

import habluetooth
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def ha_manager() -> MagicMock:
    """Mock ha manager."""
    await habluetooth.BluetoothManager().async_setup()
