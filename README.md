# Aioshelly

## Asynchronous library to control Shelly devices

## This library is under development

Requires Python >= 3.9 and uses asyncio, aiohttp and socket.

Gen1 Device (Block/CoAP) example:

```python
import asyncio
from pprint import pprint

import aiohttp

from aioshelly.block_device import COAP, BlockDevice
from aioshelly.common import ConnectionOptions
from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
)


async def test_block_device():
    """Test Gen1 Block (CoAP) based device."""
    options = ConnectionOptions("192.168.1.165", "username", "password")

    async with aiohttp.ClientSession() as aiohttp_session, COAP() as coap_context:
        try:
            device = await BlockDevice.create(aiohttp_session, coap_context, options)
        except FirmwareUnsupported as err:
            print(f"Device firmware not supported, error: {repr(err)}")
            return
        except InvalidAuthError as err:
            print(f"Invalid or missing authorization, error: {repr(err)}")
            return
        except DeviceConnectionError as err:
            print(f"Error connecting to {options.ip_address}, error: {repr(err)}")
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

from aioshelly.common import ConnectionOptions
from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
)
from aioshelly.rpc_device import RpcDevice, WsServer


async def test_rpc_device():
    """Test Gen2 RPC (WebSocket) based device."""
    options = ConnectionOptions("192.168.1.188", "username", "password")
    ws_context = WsServer()
    await ws_context.initialize(8123)

    async with aiohttp.ClientSession() as aiohttp_session:
        try:
            device = await RpcDevice.create(aiohttp_session, ws_context, options)
        except FirmwareUnsupported as err:
            print(f"Device firmware not supported, error: {repr(err)}")
            return
        except InvalidAuthError as err:
            print(f"Invalid or missing authorization, error: {repr(err)}")
            return
        except DeviceConnectionError as err:
            print(f"Error connecting to {options.ip_address}, error: {repr(err)}")
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
