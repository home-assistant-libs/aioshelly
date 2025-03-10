"""Shelly Gen2 BLE support."""

from __future__ import annotations

import logging

from habluetooth import BluetoothScanningMode, HaBluetoothConnector

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
            client=None,  # type: ignore[arg-type]
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
    if ble_config["enable"]:
        return False
    ble_enable = await device.ble_setconfig(enable=True, enable_rpc=True)
    if not ble_enable["restart_required"]:
        return False
    LOGGER.info("BLE enabled, restarting device %s:%s", device.ip_address, device.port)
    await device.trigger_reboot(3500)
    return True
