"""Common code for Shelly library."""
from __future__ import annotations

import asyncio
import ipaddress
import re
from dataclasses import dataclass
from socket import gethostbyname
from typing import Any, Union

import aiohttp

from .const import GEN1_MIN_FIRMWARE_DATE
from .exceptions import FirmwareUnsupported

FIRMWARE_PATTERN = re.compile(r"^(\d{8})")


@dataclass
class ConnectionOptions:
    """Shelly options for connection."""

    ip_address: str
    username: str | None = None
    password: str | None = None
    temperature_unit: str = "C"
    auth: aiohttp.BasicAuth | None = None

    def __post_init__(self) -> None:
        """Call after initialization."""
        if self.username is not None:
            if self.password is None:
                raise ValueError("Supply both username and password")

            object.__setattr__(
                self, "auth", aiohttp.BasicAuth(self.username, self.password)
            )


IpOrOptionsType = Union[str, ConnectionOptions]


async def process_ip_or_options(ip_or_options: IpOrOptionsType) -> ConnectionOptions:
    """Return ConnectionOptions class from ip str or ConnectionOptions."""
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

    return options


async def get_info(
    aiohttp_session: aiohttp.ClientSession, ip_address: str
) -> dict[str, Any] | None:
    """Get info from device through REST call."""
    async with aiohttp_session.get(
        f"http://{ip_address}/shelly", raise_for_status=True
    ) as resp:
        result: dict[str, Any] = await resp.json()

    if "fw" in result:
        if not gen1_supported_firmware(result["fw"]) or result["type"] in [
            "SHSW-44",
            "SHSEN-1",
        ]:
            raise FirmwareUnsupported

    return result


def gen1_supported_firmware(ver_str: str) -> bool:
    """Return True if device firmware version is supported."""
    match = FIRMWARE_PATTERN.search(ver_str)

    if match is None:
        return False

    # We compare firmware release dates because Shelly version numbering is
    # inconsistent, sometimes the word is used as the version number.
    return int(match[0]) >= GEN1_MIN_FIRMWARE_DATE
