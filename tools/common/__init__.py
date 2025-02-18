# Common tools methods
"""Methods for aioshelly cmdline tools."""

from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from aiohttp import ClientSession

from aioshelly.block_device import BLOCK_VALUE_UNIT, COAP, BlockDevice, BlockUpdateType
from aioshelly.common import ConnectionOptions, get_info
from aioshelly.const import (
    BLOCK_GENERATIONS,
    DEFAULT_HTTP_PORT,
    DEVICES,
    RPC_GENERATIONS,
)
from aioshelly.exceptions import (
    CustomPortNotSupported,
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    MacAddressMismatchError,
    ShellyError,
    WrongShellyGen,
)
from aioshelly.rpc_device import RpcDevice, RpcUpdateType, WsServer

coap_context = COAP()
ws_context = WsServer()
init_tasks_ref = set()


async def create_device(
    aiohttp_session: ClientSession,
    options: ConnectionOptions,
    gen: int | None,
) -> Any:
    """Create a device."""
    if gen is None:
        if info := await get_info(
            aiohttp_session, options.ip_address, port=options.port
        ):
            gen = info.get("gen", 1)
        else:
            raise ShellyError("Unknown Gen")

    if gen in BLOCK_GENERATIONS:
        return await BlockDevice.create(aiohttp_session, coap_context, options)

    if gen in RPC_GENERATIONS:
        return await RpcDevice.create(aiohttp_session, ws_context, options)

    raise ShellyError("Unknown Gen")


async def init_device(device: BlockDevice | RpcDevice) -> bool:
    """Initialize Shelly device."""
    port = getattr(device, "port", DEFAULT_HTTP_PORT)
    try:
        await device.initialize()
    except InvalidAuthError as err:
        print(f"Invalid or missing authorization, error: {err!r}")
    except DeviceConnectionTimeoutError as err:
        print(f"Timeout error connecting to {device.ip_address}:{port}, error: {err!r}")
    except DeviceConnectionError as err:
        print(f"Error connecting to {device.ip_address}:{port}, error: {err!r}")
    except MacAddressMismatchError as err:
        print(f"MAC address mismatch, error: {err!r}")
    except WrongShellyGen:
        print(f"Wrong Shelly generation for device {device.ip_address}:{port}")
    except CustomPortNotSupported:
        print("Custom port not supported for Gen1")
    else:
        return True

    return False


async def connect_and_print_device(
    aiohttp_session: ClientSession,
    options: ConnectionOptions,
    init: bool,
    gen: int | None,
) -> bool:
    """Connect and print device data."""
    device = await create_device(aiohttp_session, options, gen)

    if init and not await init_device(device):
        return False

    print_device(device)
    device.subscribe_updates(partial(device_updated, action=print_device))

    return True


def device_updated(
    cb_device: BlockDevice | RpcDevice,
    update_type: BlockUpdateType | RpcUpdateType,
    action: Callable[[BlockDevice | RpcDevice], None],
) -> None:
    """Device updated callback."""
    print()
    print(
        f"{datetime.now(tz=UTC).strftime('%H:%M:%S')} Device updated! ({update_type})"
    )

    if update_type in (BlockUpdateType.ONLINE, RpcUpdateType.ONLINE):
        loop = asyncio.get_running_loop()
        init_task = loop.create_task(init_device(cb_device))
        init_tasks_ref.add(init_task)
        init_task.add_done_callback(init_tasks_ref.remove)
        return

    action(cb_device)


def print_device(device: BlockDevice | RpcDevice) -> None:
    """Print device data."""
    port = getattr(device, "port", DEFAULT_HTTP_PORT)
    if not device.initialized:
        print()
        print(f"** Device @ {device.ip_address}:{port} not initialized **")
        print()
        return

    if shelly_device := DEVICES.get(device.model):
        model_name = shelly_device.name
    else:
        model_name = f"Unknown ({device.model})"
    print(f"** {device.name} - {model_name}  @ {device.ip_address}:{port} **")
    print()

    if not device.firmware_supported:
        print(f"Device firmware not supported: {device.firmware_version}")

    if device.gen in BLOCK_GENERATIONS:
        print_block_device(cast(BlockDevice, device))
    elif device.gen in RPC_GENERATIONS:
        print_rpc_device(cast(RpcDevice, device))


def print_block_device(device: BlockDevice) -> None:
    """Print block (GEN1) device data."""
    if TYPE_CHECKING:
        assert device.blocks

    for block in device.blocks:
        print(block)
        for attr, value in block.current_values().items():
            info = block.info(attr)

            _value = value if value is not None else "-"

            unit = " " + info[BLOCK_VALUE_UNIT] if BLOCK_VALUE_UNIT in info else ""

            print(f"{attr.ljust(16)}{_value}{unit}")
        print()


def print_rpc_device(device: RpcDevice) -> None:
    """Print RPC (GEN2/3/4) device data."""
    print(f"Status: {device.status}")
    print(f"Event: {device.event}")
    print(f"Connected: {device.connected}")


def close_connections(_exit_code: int = 0) -> None:
    """Close all connections before exiting."""
    coap_context.close()
    ws_context.close()
    sys.exit(_exit_code)


async def update_outbound_ws(
    options: ConnectionOptions, init: bool, ws_url: str
) -> None:
    """Update outbound WebSocket URL (Gen2/3)."""
    async with ClientSession() as aiohttp_session:
        device: RpcDevice = await create_device(aiohttp_session, options, init, 2)
        print(f"Updating outbound weboskcet URL to {ws_url}")
        print(f"Restart required: {await device.update_outbound_websocket(ws_url)}")


async def wait_for_keyboard_interrupt() -> None:
    """Wait for keyboard interrupt (Ctrl-C)."""
    sig_event = asyncio.Event()
    signal.signal(signal.SIGINT, lambda _exit_code, _frame: sig_event.set())
    await sig_event.wait()


async def check_rpc_device_supports_scripts(
    options: ConnectionOptions, gen: int | None
) -> None:
    """Check if RPC device supports scripts."""
    async with ClientSession() as aiohttp_session:
        device: RpcDevice = await create_device(aiohttp_session, options, gen)
        await device.initialize()
        print(f"Supports scripts: {await device.supports_scripts()}")
        await device.shutdown()
