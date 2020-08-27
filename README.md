# Aioshelly

## Asynchronous library to control Shelly

## This library is under development.

Requires Python 3.5 and uses asyncio, aiohttp and aiocoap.

```python
import asyncio
from pprint import pprint
import aiohttp
import aioshelly

async def main():
    async with aiohttp.ClientSession() as session:
        device = await aioshelly.Device.create("192.168.1.165", session)

        # pprint(device.d)
        # pprint(device.s)

        for block in device.blocks:
            print(block)
            pprint(block.current_values())
            print()

        await device.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

## Supported devices

- Shelly 1
- Shelly 1 PM
- Shelly 2 (relay mode for now)
- Shelly 2.5 (relay mode for now)
- Shelly 4 Pro
- Shelly H&T
- Shelly Plug
- Shelly Plug S

## Contribution guidelines

Object hierarchy and property/method names should match the [Shelly API](https://shelly-api-docs.shelly.cloud/).
