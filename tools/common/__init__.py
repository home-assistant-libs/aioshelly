# Common tools methods
"""Methods for aioshelly cmdline tools."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from typing import TYPE_CHECKING, Any, cast

import aiohttp

from aioshelly.block_device import BLOCK_VALUE_UNIT, COAP, BlockDevice, BlockUpdateType
from aioshelly.common import ConnectionOptions, get_info
from aioshelly.const import (
    BLOCK_GENERATIONS,
    DEFAULT_HTTP_PORT,
    MODEL_NAMES,
    RPC_GENERATIONS,
)
from aioshelly.exceptions import InvalidAuthError, ShellyError
from aioshelly.rpc_device import RpcDevice, RpcUpdateType, WsServer

coap_context = COAP()
ws_context = WsServer()


async def create_device(
    aiohttp_session: aiohttp.ClientSession,
    options: ConnectionOptions,
    init: bool,
    gen: int | None,
) -> Any:
    """Create a Gen1/Gen2/Gen3 device."""
    if gen is None:
        if info := await get_info(
            aiohttp_session, options.ip_address, port=options.port
        ):
            gen = info.get("gen", 1)
        else:
            raise ShellyError("Unknown Gen")

    if gen in BLOCK_GENERATIONS:
        return await BlockDevice.create(aiohttp_session, coap_context, options, init)

    if gen in RPC_GENERATIONS:
        return await RpcDevice.create(aiohttp_session, ws_context, options, init)

    raise ShellyError("Unknown Gen")


async def connect_and_print_device(
    aiohttp_session: aiohttp.ClientSession,
    options: ConnectionOptions,
    init: bool,
    gen: int | None,
) -> None:
    """Connect and print device data."""
    device = await create_device(aiohttp_session, options, init, gen)
    print_device(device)
    device.subscribe_updates(partial(device_updated, action=print_device))


def device_updated(
    cb_device: BlockDevice | RpcDevice,
    update_type: BlockUpdateType | RpcUpdateType,
    action: Callable[[BlockDevice | RpcDevice], None],
) -> None:
    """Device updated callback."""
    print()
    print(
        f"{datetime.now(tz=timezone.utc).strftime('%H:%M:%S')} "
        f"Device updated! ({update_type})"
    )
    try:
        action(cb_device)
    except InvalidAuthError:
        print("Invalid or missing authorization (from async init)")


def print_device(device: BlockDevice | RpcDevice) -> None:
    """Print device data."""
    port = getattr(device, "port", DEFAULT_HTTP_PORT)
    if not device.initialized:
        print()
        print(f"** Device @ {device.ip_address}:{port} not initialized **")
        print()
        return

    model_name = MODEL_NAMES.get(device.model) or f"Unknown ({device.model})"
    print(f"** {device.name} - {model_name}  @ {device.ip_address}:{port} **")
    print()

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
    """Print RPC (GEN2/3) device data."""
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
    async with aiohttp.ClientSession() as aiohttp_session:
        device: RpcDevice = await create_device(aiohttp_session, options, init, 2)
        print(f"Updating outbound weboskcet URL to {ws_url}")
        print(f"Restart required: {await device.update_outbound_websocket(ws_url)}")
