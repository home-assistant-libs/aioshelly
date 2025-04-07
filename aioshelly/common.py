"""Common code for Shelly library."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from dataclasses import dataclass
from socket import gethostbyname
from typing import Any

from aiohttp import BasicAuth, ClientSession, ClientTimeout
from yarl import URL

from .const import (
    CONNECT_ERRORS,
    DEFAULT_HTTP_PORT,
    DEVICE_IO_TIMEOUT,
    DEVICES,
    FIRMWARE_PATTERN,
    MIN_FIRMWARE_DATES,
)
from .exceptions import (
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidHostError,
    MacAddressMismatchError,
    ShellyError,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_IO_TIMEOUT_CLIENT_TIMEOUT = ClientTimeout(total=DEVICE_IO_TIMEOUT)


@dataclass
class ConnectionOptions:
    """Shelly options for connection."""

    ip_address: str
    username: str | None = None
    password: str | None = None
    temperature_unit: str = "C"
    auth: BasicAuth | None = None
    device_mac: str | None = None
    port: int = DEFAULT_HTTP_PORT

    def __post_init__(self) -> None:
        """Call after initialization."""
        if self.username is not None:
            if self.password is None:
                raise ValueError("Supply both username and password")

            object.__setattr__(self, "auth", BasicAuth(self.username, self.password))


IpOrOptionsType = str | ConnectionOptions


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
    aiohttp_session: ClientSession,
    ip_address: str,
    device_mac: str | None = None,
    port: int = DEFAULT_HTTP_PORT,
) -> dict[str, Any]:
    """Get info from device through REST call."""
    error: ShellyError
    try:
        async with aiohttp_session.get(
            URL.build(scheme="http", host=ip_address, port=port, path="/shelly"),
            raise_for_status=True,
            timeout=DEVICE_IO_TIMEOUT_CLIENT_TIMEOUT,
        ) as resp:
            result: dict[str, Any] = await resp.json()
    except TimeoutError as err:
        error = DeviceConnectionTimeoutError(err)
        _LOGGER.debug("host %s:%s: timeout error: %r", ip_address, port, error)
        raise error from err
    except ValueError as err:
        error = InvalidHostError(err)
        _LOGGER.debug("host %s is invalid: %r", ip_address, error)
        raise error from err
    except CONNECT_ERRORS as err:
        error = DeviceConnectionError(err)
        _LOGGER.debug("host %s:%s: error: %r", ip_address, port, error)
        raise error from err

    mac = result["mac"]
    if device_mac and device_mac != mac:
        error = MacAddressMismatchError(f"Input MAC: {device_mac}, Shelly MAC: {mac}")
        _LOGGER.debug("host %s:%s: error: %r", ip_address, port, error)
        raise error

    return result


def is_firmware_supported(gen: int, model: str, firmware_version: str) -> bool:
    """Return True if firmware is supported."""
    fw_ver: int | None
    if device := DEVICES.get(model):
        # Specific model is known
        if not device.supported:
            return False
        fw_ver = device.min_fw_date
    elif not (fw_ver := MIN_FIRMWARE_DATES.get(gen)):
        # Protection against future generations of devices.
        return False

    match = FIRMWARE_PATTERN.search(firmware_version)
    if match is None:
        return False
    # We compare firmware release dates because Shelly version numbering is
    # inconsistent, sometimes the word is used as the version number.
    return int(match[0]) >= fw_ver
