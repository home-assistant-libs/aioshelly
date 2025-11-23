"""Zeroconf helper functions for Shelly devices."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

from zeroconf import (
    DNSPointer,
    IPVersion,
    current_time_millis,
)
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

LOGGER = logging.getLogger(__name__)

# Order matters: _shelly._tcp.local. is checked first as it's Shelly-specific
# and more likely to have the device we're looking for
SHELLY_TYPES = ("_shelly._tcp.local.", "_http._tcp.local.")
SHELLY_NAME_PREFIX = "Shelly-"
CLASS_IN = 1
TYPE_PTR = 12


async def async_lookup_device_by_name(
    aiozc: AsyncZeroconf, device_name: str
) -> tuple[str, int] | None:
    """Look up a Shelly device by name via zeroconf.

    Args:
        aiozc: AsyncZeroconf instance
        device_name: Device name (e.g., "ShellyPlugUS-C049EF8873E8")

    Returns:
        Tuple of (host, port) if found, None otherwise

    """
    service_name = f"{device_name}._http._tcp.local."

    LOGGER.debug("Active lookup for: %s", service_name)
    service_info = AsyncServiceInfo("_http._tcp.local.", service_name)

    if not await service_info.async_request(aiozc.zeroconf, 5000):
        LOGGER.debug("Active lookup did not find service")
        return None

    addresses = service_info.parsed_addresses(IPVersion.V4Only)
    if not addresses or not service_info.port:
        LOGGER.debug("Active lookup found service but no IPv4 addresses or port")
        return None

    host = addresses[0]
    port = service_info.port
    LOGGER.debug("Found device via active lookup at %s:%s", host, port)
    return (host, port)


async def async_discover_devices(
    aiozc: AsyncZeroconf, timeout: float = 3.0
) -> list[AsyncServiceInfo]:
    """Discover all Shelly devices via zeroconf.

    This function searches for Shelly devices advertised under both
    _http._tcp.local. and _shelly._tcp.local. service types.

    Note:
        This function assumes that AsyncServiceBrowser instances are running
        in the background for both _http._tcp.local. and _shelly._tcp.local.
        service types. It reads from the zeroconf cache that is populated by
        these browsers.

    Args:
        aiozc: AsyncZeroconf instance
        timeout: Timeout in seconds for resolving service info (default: 3.0)

    Returns:
        List of AsyncServiceInfo objects for discovered Shelly devices

    """
    zc = aiozc.zeroconf
    now = current_time_millis()
    timeout_ms = int(timeout * 1000)

    discovered_services: dict[str, AsyncServiceInfo] = {}
    tasks: list[asyncio.Task] = []

    for service_type in SHELLY_TYPES:
        # Get all PTR records for this service type from the cache
        ptr_records = zc.cache.async_all_by_details(service_type, TYPE_PTR, CLASS_IN)

        for record in ptr_records:
            service_name = cast(DNSPointer, record).alias
            # Extract device name by splitting on first '.'
            device_name = service_name.partition(".")[0]

            # For _http._tcp.local., filter by Shelly- prefix since it
            # contains all devices. For _shelly._tcp.local., all devices
            # are Shelly devices
            if service_type == "_http._tcp.local." and not device_name.startswith(
                SHELLY_NAME_PREFIX
            ):
                continue

            # Skip if we already have this device from another service type
            if device_name in discovered_services:
                continue

            info = AsyncServiceInfo(service_type, service_name)
            discovered_services[device_name] = info

            # Try to load from cache first
            if not info.load_from_cache(zc, now):
                # If not in cache, add to tasks to request in parallel
                tasks.append(asyncio.create_task(info.async_request(zc, timeout_ms)))

    # Request all services in parallel
    if tasks:
        await asyncio.gather(*tasks)

    # Return only services with valid addresses
    return [info for info in discovered_services.values() if info.addresses]
