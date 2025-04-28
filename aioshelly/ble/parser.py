"""Shelly Gen2 BLE support."""

from __future__ import annotations

import logging
from binascii import a2b_base64
from typing import Any

LOGGER = logging.getLogger(__name__)


def parse_ble_scan_result_event(
    data: list[Any],
) -> list[tuple[str, int, bytes]]:
    """Parse BLE scan result event."""
    version: int = data[0]
    if version == 1:
        return _parse_v1(data)
    if version == 2:  # noqa: PLR2004
        return _parse_v2(data[1])
    raise ValueError(f"Unsupported BLE scan result version: {version}")


def _parse_v1(adv: list[Any]) -> list[tuple[str, int, bytes]]:
    """Convert v1 format to a list of ble tuples."""
    _, address, rssi, advertisement_data_b64, scan_response_b64 = adv
    return [
        (
            address.upper(),
            rssi,
            a2b_base64(advertisement_data_b64.encode("ascii"))
            + a2b_base64(scan_response_b64.encode("ascii")),
        )
    ]


def _parse_v2(
    advs: list[list[Any]],
) -> list[tuple[str, int, bytes]]:
    """Convert v2 format to a list of ble tuples."""
    return [
        (
            address.upper(),
            rssi,
            a2b_base64(advertisement_data_b64.encode("ascii"))
            + a2b_base64(scan_response_b64.encode("ascii")),
        )
        for address, rssi, advertisement_data_b64, scan_response_b64 in advs
    ]
