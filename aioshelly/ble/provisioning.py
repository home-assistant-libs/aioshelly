"""WiFi provisioning via BLE for Shelly devices."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ..common import ConnectionOptions
from ..rpc_device import RpcDevice
from ..rpc_device.models import ShellyWiFiNetwork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from bleak.backends.device import BLEDevice


@asynccontextmanager
async def ble_rpc_device(ble_device: BLEDevice) -> AsyncIterator[RpcDevice]:
    """Create and manage BLE RPC device connection.

    Args:
        ble_device: BLE device to connect to

    Yields:
        Initialized RPC device

    Raises:
        DeviceConnectionError: If connection to device fails

    """
    options = ConnectionOptions(ble_device=ble_device)
    device = await RpcDevice.create(
        aiohttp_session=None,
        ws_context=None,
        ip_or_options=options,
    )

    try:
        await device.initialize()
        yield device
    finally:
        await device.shutdown()


async def async_scan_wifi_networks(
    ble_device: BLEDevice,
) -> list[ShellyWiFiNetwork]:
    """Scan for WiFi networks via BLE.

    Args:
        ble_device: BLE device to connect to

    Returns:
        List of WiFi networks with ssid, rssi, auth fields

    Raises:
        DeviceConnectionError: If connection to device fails
        RpcCallError: If RPC call fails

    """
    async with ble_rpc_device(ble_device) as device:
        return await device.wifi_scan()


async def async_provision_wifi(ble_device: BLEDevice, ssid: str, password: str) -> None:
    """Provision WiFi credentials to device via BLE.

    Args:
        ble_device: BLE device to connect to
        ssid: WiFi network SSID
        password: WiFi network password

    Raises:
        DeviceConnectionError: If connection to device fails
        RpcCallError: If RPC call fails

    """
    async with ble_rpc_device(ble_device) as device:
        await device.wifi_setconfig(
            sta_ssid=ssid, sta_password=password, sta_enable=True
        )
