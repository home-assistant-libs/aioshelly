import pytest

from aioshelly.ble import create_scanner


@pytest.mark.asyncio
async def test_create_scanner_back_compat() -> None:
    """Test create scanner works without modes."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    scanner.async_on_event(
        {
            "event": "ble.scan_result",
            "data": [
                2,
                [
                    [
                        "AA:BB:CC:DD:EE:FF",
                        -50,
                        "AQIDBAUGBwgJCg==",
                        "AQIDBAUGBwgJCg==",
                    ]
                ],
            ],
        }
    )
    scanner_data = scanner.discovered_devices_and_advertisement_data
    assert "AA:BB:CC:DD:EE:FF" in scanner_data
    ble_device, advertisement_data = scanner_data["AA:BB:CC:DD:EE:FF"]
    assert advertisement_data.rssi == -50
    assert ble_device.address == "AA:BB:CC:DD:EE:FF"
