# Aioshelly

## Asynchronous library to control Shelly

## This library is under development.

Requires Python 3 and uses asyncio, aiohttp and socket.

```python
import asyncio
from pprint import pprint
import aiohttp
import aioshelly

async def main():
    options = aioshelly.ConnectionOptions("192.168.1.165", "username", "password")

    async with aiohttp.ClientSession() as aiohttp_session, aioshelly.COAP() as coap_context:
        try:
            device = await asyncio.wait_for(
                aioshelly.Device.create(aiohttp_session, coap_context, options), 5
            )
        except asyncio.TimeoutError:
            print("Timeout connecting to", ip)
            return

        for block in device.blocks:
            print(block)
            pprint(block.current_values())
            print()


if __name__ == "__main__":
    asyncio.run(main())
```

## Included examples

The repository includes two examples to quickly try it out.

Connect to a device and print its status whenever we receive a state change:

```
python3 example.py -ip <ip> [-u <username>] [-p <password]
```

Connect to all the devices in `devices.json` at once and print their status:

```
python3 example.py -d -i
```
## Show usage help:
```
python3 example.py -h
```

## Contribution guidelines

Object hierarchy and property/method names should match the [Shelly API](https://shelly-api-docs.shelly.cloud/).
