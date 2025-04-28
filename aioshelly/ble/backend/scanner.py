"""Bluetooth scanner for shelly."""

from __future__ import annotations

import logging
from typing import Any

from bluetooth_data_tools import monotonic_time_coarse
from habluetooth import BaseHaRemoteScanner

from ..const import BLE_SCAN_RESULT_EVENT
from ..parser import parse_ble_scan_result_event

LOGGER = logging.getLogger(__name__)


class ShellyBLEScanner(BaseHaRemoteScanner):
    """Scanner for shelly."""

    def async_on_event(self, event: dict[str, Any]) -> None:
        """Process an event from the shelly and ignore if its not a ble.scan_result."""
        if event.get("event") != BLE_SCAN_RESULT_EVENT:
            return

        try:
            parsed_advs = parse_ble_scan_result_event(event["data"])
        except Exception as err:
            # Broad exception catch because we have no
            # control over the data that is coming in.
            LOGGER.error("Failed to parse BLE event: %s", err, exc_info=True)
            return

        now = monotonic_time_coarse()
        for address, rssi, raw in parsed_advs:
            self._async_on_raw_advertisement(
                address,
                rssi,
                raw,
                {},
                now,
            )
