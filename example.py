# Run with python3 example.py <ip of shelly device>
import asyncio
import sys
import traceback
from datetime import datetime

import aiohttp

import aioshelly


async def cli():
    if len(sys.argv) < 2:
        print("Error! Run with <ip> or <ip> <user> <pass>")
        return

    ip = sys.argv[1]
    if len(sys.argv) > 3:
        username = sys.argv[2]
        password = sys.argv[3]
    else:
        username = None
        password = None

    options = aioshelly.ConnectionOptions(ip, username, password)

    async with aiohttp.ClientSession() as aiohttp_session, aioshelly.COAP() as coap_context:
        device = await aioshelly.Device.create(aiohttp_session, coap_context, options)

        print_device(device)

        def device_updated(device):
            print()
            print()
            print(f"{datetime.now().strftime('%H:%m:%S')} Device updated!")
            print()
            print_device(device)

        device.subscribe_updates(device_updated)

        while True:
            await asyncio.sleep(0.1)


async def test_many():
    device_options = [
        aioshelly.ConnectionOptions("192.168.1.165", "admin", "test-password"),
        aioshelly.ConnectionOptions("192.168.1.168"),
    ]

    async with aiohttp.ClientSession() as aiohttp_session, aioshelly.COAP() as coap_context:
        results = await asyncio.gather(
            *[
                connect_and_print_device(aiohttp_session, coap_context, options)
                for options in device_options
            ],
            return_exceptions=True,
        )

    for options, result in zip(device_options, results):
        if not isinstance(result, Exception):
            continue

        print()
        print(f"Error printing device @ {options.ip_address}")
        print()

        traceback.print_tb(result.__traceback__)
        print(result)


async def connect_and_print_device(aiohttp_session, coap_context, options):
    device = await aioshelly.Device.create(aiohttp_session, coap_context, options)
    print_device(device)


def print_device(device):
    # pprint(device.coap_d)
    # pprint(device.coap_s)

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


if __name__ == "__main__":
    try:
        asyncio.run(cli())
        # asyncio.run(test_many())
    except KeyboardInterrupt:
        pass
