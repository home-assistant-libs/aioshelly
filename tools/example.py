# Run with python3 example.py -h for help
"""aioshelly usage example."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import traceback
from functools import partial
from pathlib import Path

from aiohttp import ClientSession
from common import (
    check_rpc_device_supports_scripts,
    close_connections,
    coap_context,
    connect_and_print_device,
    create_device,
    device_updated,
    init_device,
    print_device,
    update_outbound_ws,
    wait_for_keyboard_interrupt,
    ws_context,
)

from aioshelly.common import ConnectionOptions
from aioshelly.const import DEFAULT_HTTP_PORT, WS_API_URL


async def test_single(options: ConnectionOptions, init: bool, gen: int | None) -> None:
    """Test single device."""
    async with ClientSession() as aiohttp_session:
        device = await create_device(aiohttp_session, options, gen)

        if init and not await init_device(device):
            return

        print_device(device)

        device.subscribe_updates(partial(device_updated, action=print_device))

        await wait_for_keyboard_interrupt()

        await device.shutdown()
        close_connections()


async def test_devices(init: bool, gen: int | None) -> None:
    """Test multiple devices."""
    options: ConnectionOptions

    with Path.open("devices.json", encoding="utf8") as fp:
        device_options = [ConnectionOptions(**json.loads(line)) for line in fp]

    async with ClientSession() as aiohttp_session:
        results = await asyncio.gather(
            *[
                asyncio.gather(
                    connect_and_print_device(aiohttp_session, options, init, gen),
                )
                for options in device_options
            ],
            return_exceptions=True,
        )

        for options, result in zip(device_options, results, strict=False):
            if isinstance(result, bool) and not result:
                print(f"Error printing device @ {options.ip_address}:{options.port}")
            elif isinstance(result, Exception):
                print()
                traceback.print_tb(result.__traceback__)
                print(result)

        await wait_for_keyboard_interrupt()
        close_connections()


def get_arguments() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="aioshelly example")
    parser.add_argument(
        "--ip_address", "-ip", type=str, help="Test single device by IP address"
    )
    parser.add_argument(
        "--device_port",
        "-dp",
        type=int,
        default=DEFAULT_HTTP_PORT,
        help="Port to use when testing single device",
    )
    parser.add_argument(
        "--coap_port",
        "-cp",
        type=int,
        default=5683,
        help="Specify CoAP UDP port (default=5683)",
    )
    parser.add_argument(
        "--ws_port",
        "-wp",
        type=int,
        default=8123,
        help="Specify WebSocket TCP port (default=8123)",
    )
    parser.add_argument(
        "--ws_api_url",
        "-au",
        type=str,
        default=WS_API_URL,
        help=f"Specify WebSocket API URL (default={WS_API_URL})",
    )
    parser.add_argument(
        "--devices",
        "-d",
        action="store_true",
        help=(
            'Connect to all the devices in "devices.json" '
            "at once and print their status"
        ),
    )
    parser.add_argument(
        "--init", "-i", action="store_true", help="Init device(s) at startup"
    )
    parser.add_argument("--username", "-u", type=str, help="Set device username")
    parser.add_argument("--password", "-p", type=str, help="Set device password")

    parser.add_argument(
        "--gen1", "-g1", action="store_true", help="Force Gen1 (CoAP) device"
    )
    parser.add_argument(
        "--gen2", "-g2", action="store_true", help="Force Gen 2 (RPC) device"
    )
    parser.add_argument(
        "--gen3", "-g3", action="store_true", help="Force Gen 3 (RPC) device"
    )
    parser.add_argument(
        "--gen4", "-g4", action="store_true", help="Force Gen 4 (RPC) device"
    )
    parser.add_argument(
        "--debug", "-deb", action="store_true", help="Enable debug level for logging"
    )
    parser.add_argument(
        "--mac", "-m", type=str, help="Optional device MAC to subscribe for updates"
    )
    parser.add_argument(
        "--update_ws",
        "-uw",
        type=str,
        help="Update outbound WebSocket (for RPC device) and exit",
    )
    parser.add_argument(
        "--listen_ip_address",
        "-lip",
        type=str,
        nargs="*",
        default=None,
        help="Listen ip address for incoming CoAP packets",
    )
    parser.add_argument(
        "--supports_scripts",
        "-ss",
        action="store_true",
        help="Check if device supports scripts",
    )

    arguments = parser.parse_args()

    return parser, arguments


async def main() -> None:
    """Run main."""
    parser, args = get_arguments()

    await coap_context.initialize(args.coap_port, args.listen_ip_address)
    await ws_context.initialize(args.ws_port, args.ws_api_url)

    if not args.init and not (args.gen1 or args.gen2 or args.gen3 or args.gen4):
        parser.error("specify gen if no device init at startup")

    gen_list = (args.gen1, args.gen2, args.gen3, args.gen4)
    if len([gen for gen in gen_list if gen]) > 1:
        parser.error(
            "You can only use one of --gen1, --gen2, --gen3 or --gen4 at a time"
        )

    gen = None
    if args.gen1:
        gen = 1
    elif args.gen2:
        gen = 2
    elif args.gen3:
        gen = 3
    elif args.gen4:
        gen = 4

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        # if gen is in args reduce logging for other gens
        if args.gen1:
            logging.getLogger("aioshelly.rpc_device").setLevel(logging.INFO)
        elif args.gen2 or args.gen3 or args.gen4:
            logging.getLogger("aioshelly.block_device").setLevel(logging.INFO)

    if args.devices:
        await test_devices(args.init, gen)
    elif args.ip_address:
        if args.username and args.password is None:
            parser.error("--username and --password must be used together")
        options = ConnectionOptions(
            args.ip_address,
            args.username,
            args.password,
            device_mac=args.mac,
            port=args.device_port,
        )
        if args.update_ws:
            await update_outbound_ws(options, args.init, args.update_ws)
        elif args.supports_scripts:
            await check_rpc_device_supports_scripts(options, gen)
        else:
            await test_single(options, args.init, gen)
    else:
        parser.error("--ip_address or --devices must be specified")


if __name__ == "__main__":
    asyncio.run(main())
