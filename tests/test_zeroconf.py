"""Tests for zeroconf helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zeroconf import IPVersion

from aioshelly.zeroconf import async_lookup_device_by_name


@pytest.mark.asyncio
async def test_lookup_device_by_name_found() -> None:
    """Test looking up a device that exists."""
    mock_aiozc = MagicMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("aioshelly.zeroconf.AsyncServiceInfo") as mock_service_info_class:
        mock_service_info = AsyncMock()
        mock_service_info_class.return_value = mock_service_info
        mock_service_info.async_request = AsyncMock(return_value=True)
        mock_service_info.parsed_addresses = MagicMock(return_value=["192.168.1.100"])
        mock_service_info.port = 80

        result = await async_lookup_device_by_name(
            mock_aiozc, "ShellyPlugUS-C049EF8873E8"
        )

        assert result == ("192.168.1.100", 80)
        mock_service_info.async_request.assert_called_once_with(
            mock_aiozc.zeroconf, 5000
        )
        mock_service_info.parsed_addresses.assert_called_once_with(IPVersion.V4Only)


@pytest.mark.asyncio
async def test_lookup_device_by_name_not_found() -> None:
    """Test looking up a device that does not exist."""
    mock_aiozc = MagicMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("aioshelly.zeroconf.AsyncServiceInfo") as mock_service_info_class:
        mock_service_info = AsyncMock()
        mock_service_info_class.return_value = mock_service_info
        mock_service_info.async_request = AsyncMock(return_value=False)

        result = await async_lookup_device_by_name(
            mock_aiozc, "ShellyPlugUS-C049EF8873E8"
        )

        assert result is None
        mock_service_info.async_request.assert_called_once_with(
            mock_aiozc.zeroconf, 5000
        )


@pytest.mark.asyncio
async def test_lookup_device_by_name_no_addresses() -> None:
    """Test looking up a device with no IPv4 addresses."""
    mock_aiozc = MagicMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("aioshelly.zeroconf.AsyncServiceInfo") as mock_service_info_class:
        mock_service_info = AsyncMock()
        mock_service_info_class.return_value = mock_service_info
        mock_service_info.async_request = AsyncMock(return_value=True)
        mock_service_info.parsed_addresses = MagicMock(return_value=[])
        mock_service_info.port = 80

        result = await async_lookup_device_by_name(
            mock_aiozc, "ShellyPlugUS-C049EF8873E8"
        )

        assert result is None


@pytest.mark.asyncio
async def test_lookup_device_by_name_no_port() -> None:
    """Test looking up a device with no port."""
    mock_aiozc = MagicMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("aioshelly.zeroconf.AsyncServiceInfo") as mock_service_info_class:
        mock_service_info = AsyncMock()
        mock_service_info_class.return_value = mock_service_info
        mock_service_info.async_request = AsyncMock(return_value=True)
        mock_service_info.parsed_addresses = MagicMock(return_value=["192.168.1.100"])
        mock_service_info.port = None

        result = await async_lookup_device_by_name(
            mock_aiozc, "ShellyPlugUS-C049EF8873E8"
        )

        assert result is None
