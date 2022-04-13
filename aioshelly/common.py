"""Common code for Shelly library."""
from __future__ import annotations

import asyncio
import ipaddress
import re
from dataclasses import dataclass
from socket import gethostbyname
from typing import Any, Union

import aiohttp
import async_timeout

from .const import GEN1_MIN_FIRMWARE_DATE, GEN2_MIN_FIRMWARE_DATE, HTTP_CALL_TIMEOUT
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
) -> dict[str, Any]:
    """Get info from device through REST call."""
    async with async_timeout.timeout(HTTP_CALL_TIMEOUT):
        async with aiohttp_session.get(
            f"http://{ip_address}/shelly", raise_for_status=True
        ) as resp:
            result: dict[str, Any] = await resp.json()

    if not shelly_supported_firmware(result):
        raise FirmwareUnsupported

    return result


def shelly_supported_firmware(result: dict[str, Any]) -> bool:
    """Return True if device firmware version is supported."""
    fw_str: str
    fw_ver: int

    if "fw" in result:
        if result["type"] in [
            "SHSW-44",
            "SHSEN-1",
        ]:
            return False
        fw_str = result["fw"]
        fw_ver = GEN1_MIN_FIRMWARE_DATE
    else:
        fw_str = result["fw_id"]
        fw_ver = GEN2_MIN_FIRMWARE_DATE

    match = FIRMWARE_PATTERN.search(fw_str)

    if match is None:
        return False

    # We compare firmware release dates because Shelly version numbering is
    # inconsistent, sometimes the word is used as the version number.
    return int(match[0]) >= fw_ver
