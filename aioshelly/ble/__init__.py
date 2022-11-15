"""Shelly Gen2 BLE support."""
from __future__ import annotations

import logging
from base64 import b64decode
from typing import Any

from bluetooth_data_tools import BLEGAPAdvertisement, parse_advertisement_data

from ..exceptions import RpcCallError
from ..rpc_device import RpcDevice
from .const import (
    BLE_CODE,
    BLE_SCAN_RESULT_VERSION,
    BLE_SCRIPT_NAME,
    VAR_ACTIVE,
    VAR_DURATION_MS,
    VAR_EVENT_TYPE,
    VAR_INTERVAL_MS,
    VAR_VERSION,
    VAR_WINDOW_MS,
)

LOGGER = logging.getLogger(__name__)


async def _async_get_scripts_by_name(device: RpcDevice) -> dict[str, int]:
    """Get scripts by name."""
    scripts = await device.script_list()
    return {script["name"]: script["id"] for script in scripts}


async def async_stop_scanner(device: RpcDevice) -> None:
    """Stop scanner."""
    script_name_to_id = await _async_get_scripts_by_name(device)
    if script_id := script_name_to_id.get(BLE_SCRIPT_NAME):
        await device.script_stop(script_id)


async def async_start_scanner(  # pylint: disable=too-many-arguments
    device: RpcDevice,
    active: bool,
    event_type: str,
    data_version: int,
    interval_ms: int,
    window_ms: int,
    duration_ms: int,
) -> None:
    """Start scanner."""
    script_name_to_id = await _async_get_scripts_by_name(device)
    if BLE_SCRIPT_NAME not in script_name_to_id:
        await device.script_create(BLE_SCRIPT_NAME)
        script_name_to_id = await _async_get_scripts_by_name(device)

    ble_script_id = script_name_to_id[BLE_SCRIPT_NAME]

    # Not using format strings here because the script
    # code contains curly braces
    code = (
        BLE_CODE.replace(VAR_ACTIVE, "true" if active else "false")
        .replace(VAR_EVENT_TYPE, event_type)
        .replace(VAR_VERSION, str(data_version))
        .replace(VAR_INTERVAL_MS, str(interval_ms))
        .replace(VAR_WINDOW_MS, str(window_ms))
        .replace(VAR_DURATION_MS, str(duration_ms))
    )

    needs_putcode = False
    try:
        code_response = await device.script_getcode(ble_script_id)
    except RpcCallError:
        # Script has no code yet
        needs_putcode = True
    else:
        needs_putcode = code_response["data"] != code

    if needs_putcode:
        # Avoid writing the flash unless we actually need to
        # update the script
        await device.script_stop(ble_script_id)
        await device.script_putcode(ble_script_id, code)

    await device.script_start(ble_script_id)


def parse_ble_scan_result_event(
    data: list[Any],
) -> tuple[str, int, BLEGAPAdvertisement]:
    """Parse BLE scan result event."""
    version: int = data[0]
    if version != BLE_SCAN_RESULT_VERSION:
        raise ValueError(f"Unsupported BLE scan result version: {version}")

    address: str = data[1]
    rssi: int = data[2]
    advertisement_data_b64: str = data[3]
    scan_response_b64: str = data[4]
    return (
        address.upper(),
        rssi,
        parse_advertisement_data(
            (b64decode(advertisement_data_b64), b64decode(scan_response_b64))
        ),
    )


async def async_ensure_ble_enabled(device: RpcDevice) -> bool:
    """Ensure BLE is enabled.

    Returns True if the device was restarted.

    Raises RpcCallError if BLE is not supported or could not
    be enabled.
    """
    ble_config = await device.ble_getconfig()
    if ble_config["enable"]:
        return False
    ble_enable = await device.ble_setconfig(enable=True, enable_rpc=True)
    if not ble_enable["restart_required"]:
        return False
    LOGGER.info("BLE enabled, restarting device %s", device.ip_address)
    await device.trigger_reboot(3500)
    return True
