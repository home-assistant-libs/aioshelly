"""Tests for zeroconf helpers."""

from __future__ import annotations

import socket
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from zeroconf import DNSPointer, IPVersion
from zeroconf.asyncio import AsyncServiceInfo

from aioshelly.zeroconf import async_discover_devices, async_lookup_device_by_name


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


def _create_shelly_service_info(
    name: str,
    service_type: str,
    address: str = "192.168.1.100",
    port: int = 80,
) -> AsyncServiceInfo:
    """Create a mock Shelly service info."""
    return AsyncServiceInfo(
        service_type,
        name,
        addresses=[socket.inet_aton(address)],
        port=port,
        properties={},
        weight=0,
        priority=0,
    )


@pytest.mark.asyncio
async def test_discover_devices_empty() -> None:
    """Test discovering devices when none are available."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc
    mock_zc.cache.async_all_by_details.return_value = []

    result = await async_discover_devices(mock_aiozc)

    assert result == []
    # Should query both service types
    assert mock_zc.cache.async_all_by_details.call_count == 2


@pytest.mark.asyncio
async def test_discover_devices_from_cache() -> None:
    """Test discovering devices that are already in cache."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc

    # Create mock PTR records for Shelly devices
    ptr_http = MagicMock(spec=DNSPointer)
    ptr_http.alias = "Shelly-PlugS-12345._http._tcp.local."
    ptr_shelly = MagicMock(spec=DNSPointer)
    ptr_shelly.alias = "Shelly-1-67890._shelly._tcp.local."

    cache_records: dict[str, list[DNSPointer]] = {
        "_http._tcp.local.": [ptr_http],
        "_shelly._tcp.local.": [ptr_shelly],
    }

    def mock_cache_lookup(
        service_type: str, _record_type: int, _record_class: int
    ) -> list[DNSPointer]:
        return cache_records.get(service_type, [])

    mock_zc.cache.async_all_by_details.side_effect = mock_cache_lookup

    with patch.multiple(
        AsyncServiceInfo,
        load_from_cache=MagicMock(return_value=True),
        addresses=PropertyMock(return_value=[socket.inet_aton("192.168.1.100")]),
    ):
        result = await async_discover_devices(mock_aiozc)

    # Should find 2 devices
    assert len(result) == 2
    assert all(isinstance(info, AsyncServiceInfo) for info in result)


@pytest.mark.asyncio
async def test_discover_devices_with_network_request() -> None:
    """Test discovering devices that need network requests."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc

    # Create mock PTR record
    ptr = MagicMock(spec=DNSPointer)
    ptr.alias = "Shelly-PlugS-12345._http._tcp.local."

    def mock_cache_lookup(
        service_type: str, _record_type: int, _record_class: int
    ) -> list[DNSPointer]:
        return [ptr] if service_type == "_http._tcp.local." else []

    mock_zc.cache.async_all_by_details.side_effect = mock_cache_lookup

    # Track async_request calls
    request_called = False

    async def mock_request(
        _self: AsyncServiceInfo, _zc: MagicMock, _timeout: int
    ) -> bool:
        nonlocal request_called
        request_called = True
        return True

    with patch.multiple(
        AsyncServiceInfo,
        load_from_cache=MagicMock(return_value=False),
        async_request=mock_request,
        addresses=PropertyMock(return_value=[socket.inet_aton("192.168.1.100")]),
    ):
        result = await async_discover_devices(mock_aiozc)

    assert len(result) == 1
    assert request_called


@pytest.mark.asyncio
async def test_discover_devices_filters_non_shelly() -> None:
    """Test that non-Shelly devices are filtered out."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc

    # Create mix of Shelly and non-Shelly PTR records
    ptr_shelly = MagicMock(spec=DNSPointer)
    ptr_shelly.alias = "Shelly-PlugS-12345._http._tcp.local."
    ptr_other = MagicMock(spec=DNSPointer)
    ptr_other.alias = "SomeOtherDevice._http._tcp.local."

    def mock_cache_lookup(
        service_type: str, _record_type: int, _record_class: int
    ) -> list[DNSPointer]:
        return [ptr_shelly, ptr_other] if service_type == "_http._tcp.local." else []

    mock_zc.cache.async_all_by_details.side_effect = mock_cache_lookup

    with patch.multiple(
        AsyncServiceInfo,
        load_from_cache=MagicMock(return_value=True),
        addresses=PropertyMock(return_value=[socket.inet_aton("192.168.1.100")]),
    ):
        result = await async_discover_devices(mock_aiozc)

    # Should only find the Shelly device
    assert len(result) == 1


@pytest.mark.asyncio
async def test_discover_devices_deduplicates_across_service_types() -> None:
    """Test that devices in both service types are deduplicated."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc

    # Same device name but different service types
    ptr_http = MagicMock(spec=DNSPointer)
    ptr_http.alias = "Shelly-PlugS-12345._http._tcp.local."
    ptr_shelly = MagicMock(spec=DNSPointer)
    ptr_shelly.alias = "Shelly-PlugS-12345._shelly._tcp.local."

    cache_records: dict[str, list[DNSPointer]] = {
        "_http._tcp.local.": [ptr_http],
        "_shelly._tcp.local.": [ptr_shelly],
    }

    def mock_cache_lookup(
        service_type: str, _record_type: int, _record_class: int
    ) -> list[DNSPointer]:
        return cache_records.get(service_type, [])

    mock_zc.cache.async_all_by_details.side_effect = mock_cache_lookup

    # Track how many times AsyncServiceInfo is created
    creation_count = 0
    original_init = AsyncServiceInfo.__init__

    def counting_init(self: AsyncServiceInfo, *args: Any, **kwargs: Any) -> None:
        nonlocal creation_count
        creation_count += 1
        original_init(self, *args, **kwargs)

    with (
        patch.object(AsyncServiceInfo, "__init__", counting_init),
        patch.multiple(
            AsyncServiceInfo,
            load_from_cache=MagicMock(return_value=True),
            addresses=PropertyMock(return_value=[socket.inet_aton("192.168.1.100")]),
        ),
    ):
        result = await async_discover_devices(mock_aiozc)

    # Should only create one AsyncServiceInfo instance due to deduplication
    assert creation_count == 1
    assert len(result) == 1


@pytest.mark.asyncio
async def test_discover_devices_filters_no_addresses() -> None:
    """Test that devices without addresses are filtered out."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc

    ptr = MagicMock(spec=DNSPointer)
    ptr.alias = "Shelly-PlugS-12345._http._tcp.local."

    def mock_cache_lookup(
        service_type: str, _record_type: int, _record_class: int
    ) -> list[DNSPointer]:
        return [ptr] if service_type == "_http._tcp.local." else []

    mock_zc.cache.async_all_by_details.side_effect = mock_cache_lookup

    with patch.multiple(
        AsyncServiceInfo,
        load_from_cache=MagicMock(return_value=True),
        addresses=PropertyMock(return_value=[]),
    ):
        result = await async_discover_devices(mock_aiozc)

    # Should filter out devices without addresses
    assert len(result) == 0


@pytest.mark.asyncio
async def test_discover_devices_timeout_parameter() -> None:
    """Test that timeout parameter is passed correctly."""
    mock_aiozc = MagicMock()
    mock_zc = MagicMock()
    mock_aiozc.zeroconf = mock_zc

    ptr = MagicMock(spec=DNSPointer)
    ptr.alias = "Shelly-PlugS-12345._http._tcp.local."

    def mock_cache_lookup(
        service_type: str, _record_type: int, _record_class: int
    ) -> list[DNSPointer]:
        return [ptr] if service_type == "_http._tcp.local." else []

    mock_zc.cache.async_all_by_details.side_effect = mock_cache_lookup

    request_timeout = None

    async def mock_request(
        _self: AsyncServiceInfo, _zc: MagicMock, timeout: int
    ) -> bool:
        nonlocal request_timeout
        request_timeout = timeout
        return True

    with patch.multiple(
        AsyncServiceInfo,
        load_from_cache=MagicMock(return_value=False),
        async_request=mock_request,
        addresses=PropertyMock(return_value=[socket.inet_aton("192.168.1.100")]),
    ):
        await async_discover_devices(mock_aiozc, timeout=5.0)

    # Should convert timeout from seconds to milliseconds
    assert request_timeout == 5000
