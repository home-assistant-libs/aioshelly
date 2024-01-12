"""Shelly Gen2 BLE support."""
from __future__ import annotations

import logging
from binascii import a2b_base64
from typing import Any

from bluetooth_data_tools import BLEGAPAdvertisement, parse_advertisement_data

LOGGER = logging.getLogger(__name__)


def parse_ble_scan_result_event(
    data: list[Any],
) -> list[tuple[str, int, BLEGAPAdvertisement]]:
    """Parse BLE scan result event."""
    version: int = data[0]
    if version == 1:
        return [_adv_to_ble_tuple(data[1])]
    elif version == 2:
        advs: list[Any] = data[1]
        return [_adv_to_ble_tuple(adv) for adv in advs]
    raise ValueError(f"Unsupported BLE scan result version: {version}")


def _adv_to_ble_tuple(adv: list[Any]) -> tuple[str, int, BLEGAPAdvertisement]:
    """Convert adv a ble tuple."""
    address: str
    rssi: int
    advertisement_data_b64: str
    scan_response_b64: str
    address, rssi, advertisement_data_b64, scan_response_b64 = adv
    return (
        address.upper(),
        rssi,
        parse_advertisement_data(
            (
                a2b_base64(advertisement_data_b64.encode("ascii")),
                a2b_base64(scan_response_b64.encode("ascii")),
            )
        ),
    )