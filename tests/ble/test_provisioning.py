"""Tests for BLE WiFi provisioning."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aioshelly.ble.provisioning import async_provision_wifi, async_scan_wifi_networks


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


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_rpc_device_class")
async def test_scan_wifi_networks_success(
    mock_ble_device: MagicMock,
    mock_rpc_device: AsyncMock,
) -> None:
    """Test scanning for WiFi networks successfully."""
    mock_rpc_device.call_rpc.return_value = {
        "results": [
            {"ssid": "Network1", "rssi": -50, "auth": 2},
            {"ssid": "Network2", "rssi": -60, "auth": 3},
        ]
    }

    result = await async_scan_wifi_networks(mock_ble_device)

    assert result == [
        {"ssid": "Network1", "rssi": -50, "auth": 2},
        {"ssid": "Network2", "rssi": -60, "auth": 3},
    ]
    mock_rpc_device.initialize.assert_called_once()
    mock_rpc_device.call_rpc.assert_called_once_with("WiFi.Scan", timeout=30)
    mock_rpc_device.shutdown.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_rpc_device_class")
async def test_scan_wifi_networks_empty_results(
    mock_ble_device: MagicMock,
    mock_rpc_device: AsyncMock,
) -> None:
    """Test scanning for WiFi networks with empty results."""
    mock_rpc_device.call_rpc.return_value = {"results": []}

    result = await async_scan_wifi_networks(mock_ble_device)

    assert result == []
    mock_rpc_device.shutdown.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_rpc_device_class")
async def test_scan_wifi_networks_no_results_key(
    mock_ble_device: MagicMock,
    mock_rpc_device: AsyncMock,
) -> None:
    """Test scanning for WiFi networks with missing results key."""
    mock_rpc_device.call_rpc.return_value = {}

    result = await async_scan_wifi_networks(mock_ble_device)

    assert result == []
    mock_rpc_device.shutdown.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_rpc_device_class")
async def test_scan_wifi_networks_exception_cleanup(
    mock_ble_device: MagicMock,
    mock_rpc_device: AsyncMock,
) -> None:
    """Test that device is shutdown even if scan fails."""
    mock_rpc_device.call_rpc.side_effect = Exception("Scan failed")

    with pytest.raises(Exception, match="Scan failed"):
        await async_scan_wifi_networks(mock_ble_device)

    # Shutdown should still be called
    mock_rpc_device.shutdown.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_rpc_device_class")
async def test_provision_wifi_success(
    mock_ble_device: MagicMock,
    mock_rpc_device: AsyncMock,
) -> None:
    """Test provisioning WiFi credentials successfully."""
    await async_provision_wifi(mock_ble_device, "MyNetwork", "MyPassword")

    mock_rpc_device.initialize.assert_called_once()
    mock_rpc_device.call_rpc.assert_called_once_with(
        "WiFi.SetConfig",
        {
            "config": {
                "sta": {
                    "ssid": "MyNetwork",
                    "pass": "MyPassword",
                    "enable": True,
                }
            }
        },
    )
    mock_rpc_device.shutdown.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_rpc_device_class")
async def test_provision_wifi_exception_cleanup(
    mock_ble_device: MagicMock,
    mock_rpc_device: AsyncMock,
) -> None:
    """Test that device is shutdown even if provisioning fails."""
    mock_rpc_device.call_rpc.side_effect = Exception("Provisioning failed")

    with pytest.raises(Exception, match="Provisioning failed"):
        await async_provision_wifi(mock_ble_device, "MyNetwork", "MyPassword")

    # Shutdown should still be called
    mock_rpc_device.shutdown.assert_called_once()
