# Aioshelly

## Asynchronous library to control Shelly devices

## This library is under development

Requires Python >= 3.9 and uses asyncio, aiohttp and socket.

### *From release 1.0.0 and up library has breaking changes to support Shelly Gen2 devices* Gen1 `Device` class moved under `block_device`

Gen1 Device (Block/CoAP) example:

```python
import asyncio
from pprint import pprint

import aiohttp
import async_timeout

from aioshelly.block_device import COAP, BlockDevice
from aioshelly.common import ConnectionOptions


async def test_block_device():
    """Test Gen1 Block (CoAP) based device."""
    options = ConnectionOptions("192.168.1.165", "username", "password")

    async with aiohttp.ClientSession() as aiohttp_session, COAP() as coap_context:
        try:
            async with async_timeout.timeout(10):
                device = await BlockDevice.create(
                    aiohttp_session, coap_context, options
                )
        except asyncio.TimeoutError:
            print("Timeout connecting to", options.ip_address)
            return

        for block in device.blocks:
            print(block)
            pprint(block.current_values())
            print()


if __name__ == "__main__":
    asyncio.run(test_block_device())
```

Gen2 (RPC/WebSocket) device example:

```python
import asyncio
from pprint import pprint

import aiohttp
import async_timeout

from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device import RpcDevice


async def test_rpc_device():
    """Test Gen2 RPC (WebSocket) based device."""
    options = ConnectionOptions("192.168.1.188", "username", "password")

    async with aiohttp.ClientSession() as aiohttp_session:
        try:
            async with async_timeout.timeout(10):
                device = await RpcDevice.create(aiohttp_session, options)
        except asyncio.TimeoutError:
            print("Timeout connecting to", ConnectionOptions.ip_address)
            return

        pprint(device.status)


if __name__ == "__main__":
    asyncio.run(test_rpc_device())
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
