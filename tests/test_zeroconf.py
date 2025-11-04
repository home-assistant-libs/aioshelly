"""Tests for zeroconf helpers."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zeroconf import IPVersion

from aioshelly.zeroconf import async_lookup_device_by_name


@pytest.fixture
def mock_aiozc() -> MagicMock:
    """Create a mock AsyncZeroconf instance."""
    mock_aiozc = MagicMock()
    mock_aiozc.zeroconf = MagicMock()
    return mock_aiozc


@pytest.fixture
def mock_service_info() -> AsyncMock:
    """Create a mock AsyncServiceInfo."""
    mock_info = AsyncMock()
    mock_info.async_request = AsyncMock()
    mock_info.parsed_addresses = MagicMock()
    mock_info.port = None
    return mock_info


@pytest.fixture
def mock_service_info_class(
    mock_service_info: AsyncMock,
) -> Generator[MagicMock]:
    """Create a mock AsyncServiceInfo class that returns the mock service info."""
    with patch("aioshelly.zeroconf.AsyncServiceInfo") as mock_class:
        mock_class.return_value = mock_service_info
        yield mock_class


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_service_info_class")
async def test_lookup_device_by_name_found(
    mock_aiozc: MagicMock,
    mock_service_info: AsyncMock,
) -> None:
    """Test looking up a device that exists."""
    mock_service_info.async_request.return_value = True
    mock_service_info.parsed_addresses.return_value = ["192.168.1.100"]
    mock_service_info.port = 80

    result = await async_lookup_device_by_name(mock_aiozc, "ShellyPlugUS-C049EF8873E8")

    assert result == ("192.168.1.100", 80)
    mock_service_info.async_request.assert_called_once_with(mock_aiozc.zeroconf, 5000)
    mock_service_info.parsed_addresses.assert_called_once_with(IPVersion.V4Only)


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_service_info_class")
async def test_lookup_device_by_name_not_found(
    mock_aiozc: MagicMock,
    mock_service_info: AsyncMock,
) -> None:
    """Test looking up a device that does not exist."""
    mock_service_info.async_request.return_value = False

    result = await async_lookup_device_by_name(mock_aiozc, "ShellyPlugUS-C049EF8873E8")

    assert result is None
    mock_service_info.async_request.assert_called_once_with(mock_aiozc.zeroconf, 5000)


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_service_info_class")
async def test_lookup_device_by_name_no_addresses(
    mock_aiozc: MagicMock,
    mock_service_info: AsyncMock,
) -> None:
    """Test looking up a device with no IPv4 addresses."""
    mock_service_info.async_request.return_value = True
    mock_service_info.parsed_addresses.return_value = []
    mock_service_info.port = 80

    result = await async_lookup_device_by_name(mock_aiozc, "ShellyPlugUS-C049EF8873E8")

    assert result is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_service_info_class")
async def test_lookup_device_by_name_no_port(
    mock_aiozc: MagicMock,
    mock_service_info: AsyncMock,
) -> None:
    """Test looking up a device with no port."""
    mock_service_info.async_request.return_value = True
    mock_service_info.parsed_addresses.return_value = ["192.168.1.100"]
    mock_service_info.port = None

    result = await async_lookup_device_by_name(mock_aiozc, "ShellyPlugUS-C049EF8873E8")

    assert result is None
