"""Common code for Shelly library."""
import re
from dataclasses import dataclass
from typing import Optional

import aiohttp

from .const import GEN1_MIN_FIRMWARE_DATE
from .exceptions import FirmwareUnsupported

FIRMWARE_PATTERN = re.compile(r"^(\d{8})")


@dataclass
class ConnectionOptions:
    """Shelly options for connection."""

    ip_address: str
    username: Optional[str] = None
    password: Optional[str] = None
    temperature_unit: str = "C"
    auth: Optional[aiohttp.BasicAuth] = None

    def __post_init__(self):
        """Call after initialization."""
        if self.username is not None:
            if self.password is None:
                raise ValueError("Supply both username and password")

            object.__setattr__(
                self, "auth", aiohttp.BasicAuth(self.username, self.password)
            )


async def get_info(aiohttp_session: aiohttp.ClientSession, ip_address):
    """Get info from device through REST call."""
    async with aiohttp_session.get(
        f"http://{ip_address}/shelly", raise_for_status=True
    ) as resp:
        result = await resp.json()

    if "fw" in result:
        if not gen1_supported_firmware(result["fw"]) or result["type"] in [
            "SHSW-44",
            "SHSEN-1",
        ]:
            raise FirmwareUnsupported

    return result


def gen1_supported_firmware(ver_str: str):
    """Return True if device firmware version is supported."""
    match = FIRMWARE_PATTERN.search(ver_str)

    if match is None:
        return False

    # We compare firmware release dates because Shelly version numbering is
    # inconsistent, sometimes the word is used as the version number.
    return int(match[0]) >= GEN1_MIN_FIRMWARE_DATE
