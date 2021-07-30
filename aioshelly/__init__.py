"""Shelly library."""
import asyncio
import ipaddress
from socket import gethostbyname
from typing import Union

import aiohttp

from .block_device import BlockDevice
from .coap import COAP
from .common import ConnectionOptions, ShellyGeneration
from .exceptions import ShellyError
from .rpc_device import RpcDevice


class Device:
    """Shelly device reppresentation."""

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        coap_context: COAP,
        ip_or_options: Union[str, ConnectionOptions],
        initialize: bool = True,
        gen=ShellyGeneration.GEN1,
    ):
        """Device creation."""
        if isinstance(ip_or_options, str):
            options = ConnectionOptions(ip_or_options)
        else:
            options = ip_or_options

        try:
            ipaddress.ip_address(options.ip_address)
        except ValueError:
            loop = asyncio.get_running_loop()
            options.ip_address = await loop.run_in_executor(
                None, gethostbyname, options.ip_address
            )

        if gen == ShellyGeneration.GEN1:
            block_instance = BlockDevice(coap_context, aiohttp_session, options)
            if initialize:
                await block_instance.initialize(True)
            else:
                await block_instance.coap_request("s")
            return block_instance

        if gen == ShellyGeneration.GEN2:
            rpc_instance = RpcDevice(aiohttp_session, options)
            if initialize:
                await rpc_instance.initialize()
            return rpc_instance

        raise ShellyError("Unknown Shelly Generation")
