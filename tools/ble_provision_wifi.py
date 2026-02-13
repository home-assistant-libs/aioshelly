"""Example of provisioning WiFi credentials via Bluetooth.

This script demonstrates how to:
1. Scan for and connect to a Shelly device via BLE
2. Scan for available WiFi networks
3. Configure WiFi credentials

Usage:
    python ble_provision_wifi.py [MAC_ADDRESS] [SSID] [PASSWORD] [-d|--debug]

    If no MAC_ADDRESS is provided, the script will scan for all Shelly devices
    and prompt you to select one.

    If no SSID/PASSWORD is provided, you will be prompted after scanning networks.

    Use -d or --debug to enable debug logging.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import platform
import sys
from contextlib import suppress

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from aioshelly.ble.manufacturer_data import parse_shelly_manufacturer_data
from aioshelly.ble.provisioning import async_provision_wifi, async_scan_wifi_networks

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


class ShellyScannerAll:
    """Scanner to find all Shelly BLE devices."""

    def __init__(self) -> None:
        """Initialize scanner."""
        self.found_devices: list[BLEDevice] = []

    def detection_callback(
        self,
        device: BLEDevice,
        advertisement_data: AdvertisementData,
    ) -> None:
        """Handle device detection."""
        # Only include devices with names starting with "Shelly"
        if (
            device.name
            and device.name.startswith("Shelly")
            and not any(d.address == device.address for d in self.found_devices)
        ):
            model_id = parse_shelly_manufacturer_data(
                advertisement_data.manufacturer_data
            ).get("model_id")
            model_id_str = f"{model_id:#04x}" if model_id else "unknown"
            print(
                f"Discovered Shelly device: {device.name} ({device.address}), "
                f"model_id: {model_id_str}"
            )
            self.found_devices.append(device)

    async def scan_for_devices(self, timeout: float = 10.0) -> list[BLEDevice]:
        """Scan for all Shelly devices and return list."""
        # On macOS, use_bdaddr=True to get real MAC addresses in callback
        scanner_kwargs: dict = {"detection_callback": self.detection_callback}
        if IS_MACOS:
            scanner_kwargs["cb"] = {"use_bdaddr": True}

        scanner = BleakScanner(**scanner_kwargs)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()
        return self.found_devices


async def main() -> None:  # noqa: PLR0915
    """Run the WiFi provisioning example."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Provision WiFi credentials to Shelly device via BLE"
    )
    parser.add_argument("mac_address", nargs="?", help="BLE MAC address of device")
    parser.add_argument("ssid", nargs="?", help="WiFi SSID")
    parser.add_argument("password", nargs="?", help="WiFi password")
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    # Check if MAC address was provided
    if args.mac_address:
        # MAC address provided, scan for specific device
        mac_address = args.mac_address.upper()
        print(f"Scanning for device {mac_address}...")
        device_scanner = DeviceScanner(mac_address)
        ble_device = await device_scanner.find_device(timeout=10.0)

        if not ble_device:
            print(f"Device {mac_address} not found or out of range")
            sys.exit(1)

        print(f"Found device: {ble_device.name or 'Unknown'} ({ble_device.address})")
    else:
        # No MAC address provided, scan for all Shelly devices
        print("Scanning for Shelly devices...")
        shelly_scanner = ShellyScannerAll()
        devices = await shelly_scanner.scan_for_devices(timeout=10.0)

        if not devices:
            print("No Shelly devices found")
            sys.exit(1)

        print(f"\nFound {len(devices)} Shelly device(s):")
        for i, dev in enumerate(devices, 1):
            print(f"  {i}. {dev.name or 'Unknown'} ({dev.address})")

        # Prompt user to select a device
        while True:
            try:
                prompt = f"\nSelect device (1-{len(devices)}): "
                choice = (await asyncio.to_thread(input, prompt)).strip()
                device_idx = int(choice) - 1
                if 0 <= device_idx < len(devices):
                    ble_device = devices[device_idx]
                    name = ble_device.name or "Unknown"
                    print(f"Selected: {name} ({ble_device.address})")
                    break
                print(f"Please enter a number between 1 and {len(devices)}")
            except (ValueError, KeyboardInterrupt):
                print("\nCancelled")
                sys.exit(1)

    # Enable debug logging if requested
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            force=True,
        )

    # Scan for available networks using the provisioning helper
    print("\nScanning for WiFi networks...")
    networks = await async_scan_wifi_networks(ble_device)

    print(f"\nFound {len(networks)} networks:")
    for i, network in enumerate(networks, 1):
        ssid = network.get("ssid", "Unknown")
        rssi = network.get("rssi", 0)
        auth = network.get("auth", 0)
        auth_str = "Open" if auth == 0 else "Secured"
        print(f"  {i}. {ssid} (Signal: {rssi} dBm, {auth_str})")

    # Get SSID and password from command line or prompt
    if args.ssid and args.password:
        ssid = args.ssid
        password = args.password
    else:
        # Prompt for SSID - can select from list or enter custom
        print()
        prompt = f"Enter network number (1-{len(networks)}) or custom SSID: "
        ssid_input = (await asyncio.to_thread(input, prompt)).strip()
        if not ssid_input:
            print("No SSID provided, skipping WiFi configuration.")
            return

        # Check if user entered a number to select from list
        try:
            network_idx = int(ssid_input) - 1
            if 0 <= network_idx < len(networks):
                ssid = networks[network_idx].get("ssid", "")
                print(f"Selected network: {ssid}")
            else:
                print(
                    f"Invalid selection. Please enter 1-{len(networks)} "
                    "or a custom SSID"
                )
                return
        except ValueError:
            # Not a number, treat as custom SSID
            ssid = ssid_input

        password = getpass.getpass("Enter WiFi password: ")

    # Provision WiFi credentials using the provisioning helper
    print(f"\nConfiguring WiFi: {ssid}")
    await async_provision_wifi(ble_device, ssid, password)
    print("WiFi configuration complete!")
    print("\nDevice should now connect to WiFi.")
    print("You can now connect to it via IP address.")


if __name__ == "__main__":
    asyncio.run(main())
