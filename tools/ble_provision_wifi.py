"""Example of provisioning WiFi credentials via Bluetooth.

This script demonstrates how to:
1. Connect to a Shelly device via BLE
2. Scan for available WiFi networks
3. Configure WiFi credentials
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device import RpcDevice

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main() -> None:
    """Run the WiFi provisioning example."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        print("Usage: python ble_provision_wifi.py <MAC_ADDRESS> [SSID] [PASSWORD]")
        print(
            "  If SSID/PASSWORD not provided, will scan and display available networks"
        )
        sys.exit(1)

    mac_address = sys.argv[1]

    # Create connection options with BLE MAC address
    options = ConnectionOptions(bluetooth_address=mac_address)

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

        # If SSID and password provided, configure WiFi
        if len(sys.argv) >= 4:  # noqa: PLR2004
            ssid = sys.argv[2]
            password = sys.argv[3]

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
