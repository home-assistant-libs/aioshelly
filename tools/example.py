# Run with python3 example.py -h for help
"""aioshelly usage example."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import traceback
from functools import partial
from types import FrameType

import aiohttp
from common import (
    close_connections,
    coap_context,
    connect_and_print_device,
    create_device,
    device_updated,
    print_device,
    update_outbound_ws,
    ws_context,
)

from aioshelly.common import ConnectionOptions
from aioshelly.const import WS_API_URL
from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
    MacAddressMismatchError,
    WrongShellyGen,
)


async def test_single(options: ConnectionOptions, init: bool, gen: int | None) -> None:
    """Test single device."""
    async with aiohttp.ClientSession() as aiohttp_session:
        try:
            device = await create_device(aiohttp_session, options, init, gen)
        except FirmwareUnsupported as err:
            print(f"Device firmware not supported, error: {repr(err)}")
            return
        except InvalidAuthError as err:
            print(f"Invalid or missing authorization, error: {repr(err)}")
            return
        except DeviceConnectionError as err:
            print(f"Error connecting to {options.ip_address}, error: {repr(err)}")
            return
        except MacAddressMismatchError as err:
            print(f"MAC address mismatch, error: {repr(err)}")
            return
        except WrongShellyGen:
            print(f"Wrong Shelly generation {gen}, device gen: {2 if gen==1 else 1}")
            return

        print_device(device)

        device.subscribe_updates(partial(device_updated, action=print_device))

        while True:
            await asyncio.sleep(0.1)


async def test_devices(init: bool, gen: int | None) -> None:
    """Test multiple devices."""
    device_options = []
    with open("devices.json", encoding="utf8") as fp:
        for line in fp:
            device_options.append(ConnectionOptions(**json.loads(line)))

    async with aiohttp.ClientSession() as aiohttp_session:
        results = await asyncio.gather(
            *[
                asyncio.gather(
                    connect_and_print_device(aiohttp_session, options, init, gen),
                )
                for options in device_options
            ],
            return_exceptions=True,
        )

        for options, result in zip(device_options, results):
            if not isinstance(result, Exception):
                continue

            print()
            print(f"Error printing device @ {options.ip_address}")

            if isinstance(result, FirmwareUnsupported):
                print("Device firmware not supported")
            elif isinstance(result, InvalidAuthError):
                print("Invalid or missing authorization")
            elif isinstance(result, DeviceConnectionError):
                print("Error connecting to device")
            elif isinstance(result, MacAddressMismatchError):
                print("MAC address mismatch error")
            elif isinstance(result, WrongShellyGen):
                print("Wrong Shelly generation")
            else:
                print()
                traceback.print_tb(result.__traceback__)
                print(result)

        while True:
            await asyncio.sleep(0.1)


def get_arguments() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="aioshelly example")
    parser.add_argument(
        "--ip_address", "-ip", type=str, help="Test single device by IP address"
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
        help='Connect to all the devices in "devices.json" at once and print their status',
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
        "--debug", "-deb", action="store_true", help="Enable debug level for logging"
    )
    parser.add_argument(
        "--mac", "-m", type=str, help="Optional device MAC to subscribe for updates"
    )

    parser.add_argument(
        "--update_ws",
        "-uw",
        type=str,
        help="Update outbound WebSocket (Gen2/3) and exit",
    )

    arguments = parser.parse_args()

    return parser, arguments


async def main() -> None:
    """Run main."""
    parser, args = get_arguments()

    await coap_context.initialize(args.coap_port)
    await ws_context.initialize(args.ws_port, args.ws_api_url)

    if not args.init and not (args.gen1 or args.gen2 or args.gen3):
        parser.error("specify gen if no device init at startup")
    if args.gen1 and args.gen2:
        parser.error("--gen1 and --gen2 can't be used together")
    elif args.gen1 and args.gen3:
        parser.error("--gen1 and --gen3 can't be used together")
    elif args.gen2 and args.gen3:
        parser.error("--gen2 and --gen3 can't be used together")

    gen = None
    if args.gen1:
        gen = 1
    elif args.gen2:
        gen = 2
    elif args.gen3:
        gen = 3

    if args.debug:
        logging.basicConfig(level="DEBUG", force=True)

    def handle_sigint(_exit_code: int, _frame: FrameType) -> None:
        """Handle Keyboard signal interrupt (ctrl-c)."""
        close_connections(_exit_code)

    signal.signal(signal.SIGINT, handle_sigint)  # type: ignore [func-returns-value]

    if args.devices:
        await test_devices(args.init, gen)
    elif args.ip_address:
        if args.username and args.password is None:
            parser.error("--username and --password must be used together")
        options = ConnectionOptions(
            args.ip_address, args.username, args.password, device_mac=args.mac
        )
        if args.update_ws:
            await update_outbound_ws(options, args.init, args.update_ws)
        else:
            await test_single(options, args.init, gen)
    else:
        parser.error("--ip_address or --devices must be specified")


if __name__ == "__main__":
    asyncio.run(main())
