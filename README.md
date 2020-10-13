# Aioshelly

## Asynchronous library to control Shelly

## This library is under development.

Requires Python 3 and uses asyncio, aiohttp and aiocoap.

```python
import asyncio
from pprint import pprint
import aiocoap
import aiohttp
import aioshelly

async def main():
    options = aioshelly.ConnectionOptions("192.168.1.165", "username", "password")

    coap_context = await aiocoap.Context.create_client_context()

    async with aiohttp.ClientSession() as session:
        device = await aioshelly.Device.create(session, options)

        for block in device.blocks:
            print(block)
            pprint(block.current_values())
            print()

    await coap_context.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

## Breaking changes for 0.3.3+

Due to the code quality checks, we changed a few methods/properties:

- `ip()` is now `ip_address()`
- `d`    is now `coap_d`
- `s`    is now `coap_s`

## Contribution guidelines

Object hierarchy and property/method names should match the [Shelly API](https://shelly-api-docs.shelly.cloud/).
