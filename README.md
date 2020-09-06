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
        device = await aioshelly.Device.create(session, "192.168.1.165")

        for block in device.blocks:
            print(block)
            pprint(block.current_values())
            print()

        await device.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

## Contribution guidelines

Object hierarchy and property/method names should match the [Shelly API](https://shelly-api-docs.shelly.cloud/).
