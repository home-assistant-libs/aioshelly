"""Shelly Gen2 BLE support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from habluetooth import BluetoothScanningMode, HaBluetoothConnector

from ..const import MODEL_ID_TO_DEVICE
from ..exceptions import RpcCallError
from ..rpc_device import RpcDevice
from .backend.scanner import ShellyBLEScanner
from .const import (
    BLE_CODE,
    BLE_SCRIPT_NAME,
    VAR_ACTIVE,
    VAR_EVENT_TYPE,
    VAR_VERSION,
)

if TYPE_CHECKING:
    from ..const import ShellyDevice

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


async def async_start_scanner(
    device: RpcDevice, active: bool, event_type: str, data_version: int
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


async def async_get_ble_script_id(device: RpcDevice) -> int | None:
    """Return the installed BLE integration script id, or None if absent.

    Callers that toggle active mode repeatedly (e.g. the active-window
    scheduler) should resolve the id once and cache it for the
    lifetime of the script, since the id is stable until the script
    is recreated.
    """
    script_name_to_id = await _async_get_scripts_by_name(device)
    return script_name_to_id.get(BLE_SCRIPT_NAME)


async def async_set_active_mode(
    device: RpcDevice, script_id: int, active: bool
) -> None:
    """Flip the BLE scanner's active mode via Script.Eval.

    The script body exposes a ``setActive(v)`` function (see BLE_CODE
    in const.py) that stops and restarts BLE.Scanner with the new
    active flag. Driving the toggle via Script.Eval keeps the script
    body byte-identical across windows, so the device's flash is not
    rewritten on every transition.

    ``script_id`` must be the id returned by ``async_get_ble_script_id``
    or otherwise known to the caller. This keeps each flip a single
    Script.Eval round-trip with no Script.List overhead.
    """
    await device.script_eval(script_id, f"setActive({'true' if active else 'false'})")


def create_scanner(
    source: str,
    name: str,
    requested_mode: BluetoothScanningMode | None = None,
    current_mode: BluetoothScanningMode | None = None,
) -> ShellyBLEScanner:
    """Create scanner."""
    return ShellyBLEScanner(
        source,
        name,
        HaBluetoothConnector(
            # no active connections to shelly yet
            client=None,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            source=source,
            can_connect=lambda: False,
        ),
        False,
        requested_mode=requested_mode,
        current_mode=current_mode,
    )


async def async_ensure_ble_enabled(device: RpcDevice) -> bool:
    """Ensure BLE is enabled.

    Returns True if the device was restarted.

    Raises RpcCallError if BLE is not supported or could not
    be enabled.
    """
    ble_config = await device.ble_getconfig()
    # The enable property has been removed in firmware 2.0.0.
    # Bluetooth scanning now auto-activates when needed by scripts.
    if ble_config.get("enable", True):
        return False
    ble_enable = await device.ble_setconfig(enable=True, enable_rpc=False)
    if not ble_enable["restart_required"]:
        return False
    LOGGER.info("BLE enabled, restarting device %s:%s", device.ip_address, device.port)
    await device.trigger_reboot(3500)
    return True


def get_device_from_model_id(model_id: int) -> ShellyDevice | None:
    """Get the ShellyDevice from a BLE model ID.

    Args:
        model_id: Model ID from BLE manufacturer data

    Returns:
        ShellyDevice object or None if not found

    """
    return MODEL_ID_TO_DEVICE.get(model_id)


def get_name_from_model_id(model_id: int) -> str | None:
    """Get the device name from a BLE model ID.

    Args:
        model_id: Model ID from BLE manufacturer data

    Returns:
        Device name or None if not found

    """
    if device := get_device_from_model_id(model_id):
        return device.name
    return None
