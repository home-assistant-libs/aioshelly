# Run with python3 example.py <ip of shelly device>
import asyncio
import sys

import aiohttp

import aioshelly


async def main():

    ip = sys.argv[1]
    if len(sys.argv) > 3:
        username = sys.argv[2]
        password = sys.argv[3]
    else:
        username = None
        password = None

    options = aioshelly.ConnectionOptions(ip, username, password)

    async with aiohttp.ClientSession() as session:
        device = await aioshelly.Device.create(session, options)

        # pprint(device.coap_d)
        # pprint(device.coap_s)

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

        await device.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
