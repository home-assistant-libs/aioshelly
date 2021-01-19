# Run with python3 example.py <ip of shelly device>
import argparse
import asyncio
import json
import sys
import traceback
from datetime import datetime

import aiohttp

import aioshelly


async def test_single(ip, username, password, init, timeout):
    options = aioshelly.ConnectionOptions(ip, username, password)

    async with aiohttp.ClientSession() as aiohttp_session, aioshelly.COAP() as coap_context:
        try:
            device = await asyncio.wait_for(
                aioshelly.Device.create(aiohttp_session, coap_context, options, init),
                timeout,
            )
        except asyncio.TimeoutError:
            print("Timeout connecting to", ip)
            return

        print_device(device)

        device.subscribe_updates(device_updated)

        while True:
            await asyncio.sleep(0.1)


async def test_devices(init, timeout):
    device_options = []
    with open("devices.json") as fp:
        for line in fp:
            device_options.append(aioshelly.ConnectionOptions(**json.loads(line)))

    async with aiohttp.ClientSession() as aiohttp_session, aioshelly.COAP() as coap_context:
        results = await asyncio.gather(
            *[
                asyncio.wait_for(
                    connect_and_print_device(
                        aiohttp_session, coap_context, options, init
                    ),
                    timeout,
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

            if isinstance(result, asyncio.TimeoutError):
                print("Timeout connecting to device")
            else:
                print()
                traceback.print_tb(result.__traceback__)
                print(result)

        while True:
            await asyncio.sleep(0.1)


async def connect_and_print_device(aiohttp_session, coap_context, options, init):
    device = await aioshelly.Device.create(aiohttp_session, coap_context, options, init)
    print_device(device)
    device.subscribe_updates(device_updated)


def device_updated(cb_device):
    print()
    print()
    print(f"{datetime.now().strftime('%H:%M:%S')} Device updated!")
    print()
    print_device(cb_device)


def print_device(device):
    if not device.initialized:
        print()
        print(f"** Device @ {device.ip_address} not initialized **")
        print()
        return

    model = (
        aioshelly.MODEL_NAMES.get(device.settings["device"]["type"])
        or f'Unknown model {device.settings["device"]["type"]}'
    )

    print()
    print(f"** {model} @ {device.ip_address} **")
    print()

    light_relay_block = None

    for block in device.blocks:
        print(block)
        for attr, value in block.current_values().items():
            info = block.info(attr)

            if value is None:
                value = "-"

            if aioshelly.BLOCK_VALUE_UNIT in info:
                unit = " " + info[aioshelly.BLOCK_VALUE_UNIT]
            else:
                unit = ""

            print(f"{attr.ljust(16)}{value}{unit}")
        print()

        if light_relay_block is None and block.type in ("relay", "light"):
            light_relay_block = block

    # if light_relay_block:
    #     print(
    #         await light_relay_block.set_state(
    #             turn="off" if light_relay_block.output else "on"
    #         )
    #     )


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="aioshelly example")
    parser.add_argument(
        "--ip_address", "-ip", type=str, help="Test single device by IP address"
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
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=5,
        help="Device init timeout in seconds (default=5)",
    )
    parser.add_argument("--username", "-u", type=str, help="Set device username")
    parser.add_argument("--password", "-p", type=str, help="Set device password")

    arguments = parser.parse_args()

    return parser, arguments


async def main() -> None:
    """Run main."""
    parser, args = get_arguments()
    if args.devices:
        await test_devices(args.init, args.timeout)
    elif args.ip_address:
        if args.username and args.password is None:
            parser.error("--username and --password must be used together")
        await test_single(
            args.ip_address, args.username, args.password, args.init, args.timeout
        )
    else:
        parser.error("--ip_address or --devices must be specified")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
