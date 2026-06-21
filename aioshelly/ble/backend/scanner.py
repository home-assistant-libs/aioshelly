"""Bluetooth scanner for shelly."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from bluetooth_data_tools import monotonic_time_coarse
from habluetooth import BaseHaRemoteScanner, BluetoothScanningMode

from aioshelly import ble as _ble

from ...exceptions import ShellyError
from ..const import BLE_SCAN_RESULT_EVENT
from ..parser import parse_ble_scan_result_event

if TYPE_CHECKING:
    from ...rpc_device import RpcDevice

LOGGER = logging.getLogger(__name__)


class ShellyBLEScanner(BaseHaRemoteScanner):
    """Scanner for shelly."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the scanner."""
        super().__init__(*args, **kwargs)
        self._active_window_device: RpcDevice | None = None
        self._active_window_script_id: int | None = None
        self._active_window_lock = asyncio.Lock()

    def set_active_window_provider(self, device: RpcDevice) -> None:
        """Bind the RpcDevice used to flip the BLE script for active windows.

        Without this, async_request_active_window is a no-op returning
        False (matching the BaseHaScanner default).
        """
        self._active_window_device = device

    async def async_request_active_window(self, duration: float) -> bool:
        """Flip the Shelly's BLE script to active for ``duration`` seconds.

        Called by habluetooth's auto-mode scheduler. The Shelly BLE
        script's scanner is flipped to active mode via Script.Eval,
        then reverted to passive once the window ends. Only one window
        may be open at a time; a request that arrives while another
        window is in flight returns ``False`` immediately so the
        caller can decide whether to retry.
        """
        device = self._active_window_device
        if device is None:
            return False
        if self._active_window_lock.locked():
            return False

        async with self._active_window_lock:
            script_id = self._active_window_script_id
            if script_id is None:
                try:
                    script_id = await _ble.async_get_ble_script_id(device)
                except ShellyError as err:
                    LOGGER.debug(
                        "%s: failed to resolve BLE script id: %s", self.name, err
                    )
                    return False
                if script_id is None:
                    LOGGER.debug(
                        "%s: BLE script not installed, skipping active window",
                        self.name,
                    )
                    return False
                self._active_window_script_id = script_id
            try:
                await _ble.async_set_active_mode(device, script_id, active=True)
            except ShellyError as err:
                LOGGER.debug(
                    "%s: failed to enter active scan window: %s", self.name, err
                )
                return False
            previous_mode = self.current_mode
            self.set_current_mode(BluetoothScanningMode.ACTIVE)
            try:
                await asyncio.sleep(duration)
            finally:
                try:
                    try:
                        await _ble.async_set_active_mode(
                            device, script_id, active=False
                        )
                    except ShellyError as err:
                        # Restore failures almost always mean the WS to the
                        # device dropped, in which case habluetooth's reload
                        # cycle restarts the scanner anyway. Otherwise the
                        # device stays in active mode until the next window's
                        # restore succeeds or the device reboots; both are
                        # acceptable for a battery safeguard. Surface at
                        # warning so operators can still see it.
                        LOGGER.warning(
                            "%s: failed to restore scan mode after active window: %s",
                            self.name,
                            err,
                        )
                finally:
                    # Always reflect that the window has ended, even if the
                    # restore RPC was cancelled or raised an unexpected error.
                    # The device may still be sweeping actively, but
                    # habluetooth's reload cycle reconciles on the next
                    # scanner start, and leaving current_mode stuck at ACTIVE
                    # would mislead the manager and UI indefinitely.
                    self.set_current_mode(previous_mode)
        return True

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
