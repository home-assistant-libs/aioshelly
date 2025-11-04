"""Tests for BLE WiFi provisioning."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aioshelly.ble.provisioning import async_provision_wifi, async_scan_wifi_networks


@pytest.mark.asyncio
async def test_scan_wifi_networks_success() -> None:
    """Test scanning for WiFi networks successfully."""
    mock_ble_device = MagicMock()

    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_rpc_device_class:
        mock_device = AsyncMock()
        mock_rpc_device_class.create = AsyncMock(return_value=mock_device)
        mock_device.initialize = AsyncMock()
        mock_device.call_rpc = AsyncMock(
            return_value={
                "results": [
                    {"ssid": "Network1", "rssi": -50, "auth": 2},
                    {"ssid": "Network2", "rssi": -60, "auth": 3},
                ]
            }
        )
        mock_device.shutdown = AsyncMock()

        result = await async_scan_wifi_networks(mock_ble_device)

        assert result == [
            {"ssid": "Network1", "rssi": -50, "auth": 2},
            {"ssid": "Network2", "rssi": -60, "auth": 3},
        ]
        mock_device.initialize.assert_called_once()
        mock_device.call_rpc.assert_called_once_with("WiFi.Scan", timeout=30)
        mock_device.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_scan_wifi_networks_empty_results() -> None:
    """Test scanning for WiFi networks with empty results."""
    mock_ble_device = MagicMock()

    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_rpc_device_class:
        mock_device = AsyncMock()
        mock_rpc_device_class.create = AsyncMock(return_value=mock_device)
        mock_device.initialize = AsyncMock()
        mock_device.call_rpc = AsyncMock(return_value={"results": []})
        mock_device.shutdown = AsyncMock()

        result = await async_scan_wifi_networks(mock_ble_device)

        assert result == []
        mock_device.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_scan_wifi_networks_no_results_key() -> None:
    """Test scanning for WiFi networks with missing results key."""
    mock_ble_device = MagicMock()

    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_rpc_device_class:
        mock_device = AsyncMock()
        mock_rpc_device_class.create = AsyncMock(return_value=mock_device)
        mock_device.initialize = AsyncMock()
        mock_device.call_rpc = AsyncMock(return_value={})
        mock_device.shutdown = AsyncMock()

        result = await async_scan_wifi_networks(mock_ble_device)

        assert result == []
        mock_device.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_scan_wifi_networks_exception_cleanup() -> None:
    """Test that device is shutdown even if scan fails."""
    mock_ble_device = MagicMock()

    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_rpc_device_class:
        mock_device = AsyncMock()
        mock_rpc_device_class.create = AsyncMock(return_value=mock_device)
        mock_device.initialize = AsyncMock()
        mock_device.call_rpc = AsyncMock(side_effect=Exception("Scan failed"))
        mock_device.shutdown = AsyncMock()

        with pytest.raises(Exception, match="Scan failed"):
            await async_scan_wifi_networks(mock_ble_device)

        # Shutdown should still be called
        mock_device.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_provision_wifi_success() -> None:
    """Test provisioning WiFi credentials successfully."""
    mock_ble_device = MagicMock()

    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_rpc_device_class:
        mock_device = AsyncMock()
        mock_rpc_device_class.create = AsyncMock(return_value=mock_device)
        mock_device.initialize = AsyncMock()
        mock_device.call_rpc = AsyncMock()
        mock_device.shutdown = AsyncMock()

        await async_provision_wifi(mock_ble_device, "MyNetwork", "MyPassword")

        mock_device.initialize.assert_called_once()
        mock_device.call_rpc.assert_called_once_with(
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
        mock_device.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_provision_wifi_exception_cleanup() -> None:
    """Test that device is shutdown even if provisioning fails."""
    mock_ble_device = MagicMock()

    with patch("aioshelly.ble.provisioning.RpcDevice") as mock_rpc_device_class:
        mock_device = AsyncMock()
        mock_rpc_device_class.create = AsyncMock(return_value=mock_device)
        mock_device.initialize = AsyncMock()
        mock_device.call_rpc = AsyncMock(side_effect=Exception("Provisioning failed"))
        mock_device.shutdown = AsyncMock()

        with pytest.raises(Exception, match="Provisioning failed"):
            await async_provision_wifi(mock_ble_device, "MyNetwork", "MyPassword")

        # Shutdown should still be called
        mock_device.shutdown.assert_called_once()
