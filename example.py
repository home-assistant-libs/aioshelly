# Run with python3 example.py <ip of shelly device>
import asyncio
import sys
from pprint import pprint

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

    async with aiohttp.ClientSession() as session:
        device = await aioshelly.Device.create(ip, session, username, password)

        # pprint(device.d)
        # pprint(device.s)

        for block in device.blocks:
            print(block)
            pprint(block.current_values())
            print()

        # print(await device.blocks[0].toggle())

        await device.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
