"""Tests for the BLE."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import habluetooth
import pytest
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def ha_manager() -> MagicMock:
    """Mock ha manager."""
    await habluetooth.BluetoothManager().async_setup()


@pytest.fixture
def mock_ble_device() -> MagicMock:
    """Create a mock BLE device."""
    return MagicMock()


@pytest.fixture
def mock_rpc_device() -> AsyncMock:
    """Create a mock RPC device."""
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.call_rpc = AsyncMock()
    mock_device.wifi_scan = AsyncMock()
    mock_device.wifi_setconfig = AsyncMock()
    mock_device.shutdown = AsyncMock()
    return mock_device


@pytest.fixture
def mock_rpc_device_class(
    mock_rpc_device: AsyncMock,
) -> Generator[MagicMock]:
    """Create a mock RPC device class that returns the mock device."""
    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_class:
        mock_class.create = AsyncMock(return_value=mock_rpc_device)
        yield mock_class
