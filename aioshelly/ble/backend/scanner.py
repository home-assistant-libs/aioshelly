"""Bluetooth scanner for shelly."""
from __future__ import annotations

import logging
from typing import Any

from bluetooth_data_tools import monotonic_time_coarse
from habluetooth import BaseHaRemoteScanner

from ..const import BLE_SCAN_RESULT_EVENT, BLE_SCAN_RESULT_VERSION
from ..parser import parse_ble_scan_result_event

LOGGER = logging.getLogger(__name__)


class ShellyBLEScanner(BaseHaRemoteScanner):
    """Scanner for shelly."""

    def async_on_event(self, event: dict[str, Any]) -> None:
        """Process an event from the shelly and ignore if its not a ble.scan_result."""
        if event.get("event") != BLE_SCAN_RESULT_EVENT:
            return

        data = event["data"]

        if data[0] != BLE_SCAN_RESULT_VERSION:
            LOGGER.warning("Unsupported BLE scan result version: %s", data[0])
            return

        try:
            parsed_advs = parse_ble_scan_result_event(data)
        except Exception as err:  # pylint: disable=broad-except
            # Broad exception catch because we have no
            # control over the data that is coming in.
            LOGGER.error("Failed to parse BLE event: %s", err, exc_info=True)
            return

        now = monotonic_time_coarse()
        for address, rssi, parsed in parsed_advs:
            self._async_on_advertisement(
                address,
                rssi,
                parsed.local_name,
                parsed.service_uuids,
                parsed.service_data,
                parsed.manufacturer_data,
                parsed.tx_power,
                {},
                now,
            )
