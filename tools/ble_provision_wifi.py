"""Example of provisioning WiFi credentials via Bluetooth.

This script demonstrates how to:
1. Scan for and connect to a Shelly device via BLE
2. Scan for available WiFi networks
3. Configure WiFi credentials
"""

from __future__ import annotations

import asyncio
import getpass
import logging
import platform
import sys
from contextlib import suppress

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device import RpcDevice

# Check if we're on macOS
IS_MACOS = platform.system() == "Darwin"


class DeviceScanner:
    """Scanner to find a specific BLE device by MAC address."""

    def __init__(self, mac_address: str) -> None:
        """Initialize scanner."""
        self.mac_address = mac_address.upper()
        self.found_event = asyncio.Event()
        self.found_device: BLEDevice | None = None

    def detection_callback(
        self,
        device: BLEDevice,
        advertisement_data: AdvertisementData,  # noqa: ARG002
    ) -> None:
        """Handle device detection."""
        if device.address.upper() == self.mac_address:
            self.found_device = device
            self.found_event.set()

    async def find_device(self, timeout: float = 10.0) -> BLEDevice | None:
        """Scan for device and return it if found."""
        # On macOS, use_bdaddr=True to get real MAC addresses in callback
        scanner_kwargs: dict = {"detection_callback": self.detection_callback}
        if IS_MACOS:
            scanner_kwargs["cb"] = {"use_bdaddr": True}

        scanner = BleakScanner(**scanner_kwargs)
        await scanner.start()
        with suppress(TimeoutError):
            await asyncio.wait_for(self.found_event.wait(), timeout=timeout)
        await scanner.stop()
        return self.found_device


async def main() -> None:
    """Run the WiFi provisioning example."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        print("Usage: python ble_provision_wifi.py <MAC_ADDRESS> [SSID] [PASSWORD]")
        print("  If SSID/PASSWORD not provided, you will be prompted after scanning")
        sys.exit(1)

    mac_address = sys.argv[1].upper()

    # Scan for the BLE device
    print(f"Scanning for device {mac_address}...")
    device_scanner = DeviceScanner(mac_address)
    ble_device = await device_scanner.find_device(timeout=10.0)

    if not ble_device:
        print(f"Device {mac_address} not found or out of range")
        sys.exit(1)

    print(f"Found device: {ble_device.name or 'Unknown'} ({ble_device.address})")

    # Enable debug logging after finding device to avoid spam during scan
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )

    # Create connection options with BLE device
    options = ConnectionOptions(ble_device=ble_device)

    # Create device (uses BLE transport based on connection options)
    device = await RpcDevice.create(
        aiohttp_session=None,
        ws_context=None,
        ip_or_options=options,
    )

    try:
        # Initialize device connection
        await device.initialize()

        # Get device info
        print(f"Connected to: {device.model}")
        print(f"Firmware: {device.firmware_version}")

        # Scan for available networks
        print("\nScanning for WiFi networks...")
        scan_result = await device.call_rpc("WiFi.Scan")
        networks = scan_result.get("results", [])

        print(f"\nFound {len(networks)} networks:")
        for i, network in enumerate(networks, 1):
            ssid = network.get("ssid", "Unknown")
            rssi = network.get("rssi", 0)
            auth = network.get("auth", 0)
            auth_str = "Open" if auth == 0 else "Secured"
            print(f"  {i}. {ssid} (Signal: {rssi} dBm, {auth_str})")

        # Get SSID and password from command line or prompt
        if len(sys.argv) >= 4:  # noqa: PLR2004
            ssid = sys.argv[2]
            password = sys.argv[3]
        else:
            # Prompt for SSID and password
            print()
            ssid = input("Enter WiFi SSID: ").strip()
            if not ssid:
                print("No SSID provided, skipping WiFi configuration.")
                return
            password = getpass.getpass("Enter WiFi password: ")

        print(f"\nConfiguring WiFi: {ssid}")
        result = await device.call_rpc(
            "WiFi.SetConfig",
            {
                "config": {
                    "sta": {
                        "ssid": ssid,
                        "pass": password,
                        "enable": True,
                    }
                }
            },
        )
        print(f"WiFi configuration result: {result}")
        print("\nDevice should now connect to WiFi.")
        print("You can now connect to it via IP address.")

    finally:
        await device.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
