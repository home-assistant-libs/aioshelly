"""Tests for common module."""

from unittest.mock import patch

import pytest
from aiohttp import BasicAuth, ClientError, ClientSession
from aioresponses import aioresponses
from yarl import URL

from aioshelly.common import (
    ConnectionOptions,
    get_info,
    is_firmware_supported,
    process_ip_or_options,
)
from aioshelly.const import DEFAULT_HTTP_PORT
from aioshelly.exceptions import (
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidHostError,
    MacAddressMismatchError,
)

from .rpc_device import load_device_fixture


@pytest.mark.parametrize(
    ("gen", "model", "firmware_version", "expected"),
    [
        (5, "XYZ-G5", "20250913-112054/v1.0.0-gcb84623", False),
        (4, "XYZ-G4", "20240913-112054/v1.0.0-gcb84623", True),
        (1, "SHSW-44", "20230913-112054/v1.14.0-gcb84623", False),
        (1, "SHSW-1", "20230913-112054/v1.14.0-gcb84623", True),
        (2, "SNDC-0D4P10WW", "20230703-112054/0.99.0-gcb84623", False),
        (3, "UNKNOWN", "20240819-074343/1.4.20-gc2639da", True),
        (3, "S3SW-002P16EU", "strange-firmware-version", False),
    ],
)
def test_is_firmware_supported(
    gen: int, model: str, firmware_version: str, expected: bool
) -> None:
    """Test is_firmware_supported function."""
    assert is_firmware_supported(gen, model, firmware_version) is expected


@pytest.mark.asyncio
async def test_process_ip_or_options() -> None:
    """Test process_ip_or_options function."""
    ip = "192.168.20.11"

    # Test string numeric IP address
    assert await process_ip_or_options(ip) == ConnectionOptions(ip)

    # Test string hostname IP address
    with patch("aioshelly.common.gethostbyname", return_value=ip):
        assert await process_ip_or_options("some_host") == ConnectionOptions(ip)

    # Test ConnectionOptions
    options = ConnectionOptions(ip, "user", "pass")
    assert await process_ip_or_options(options) == options
    assert options.auth == BasicAuth("user", "pass")

    # Test missing password
    with pytest.raises(ValueError, match="Supply both username and password"):
        options = ConnectionOptions(ip, "user")


@pytest.mark.asyncio
async def test_get_info() -> None:
    """Test get_info function."""
    mock_response = await load_device_fixture("shellyplus2pm", "shelly.json")
    ip_address = "10.10.10.10"

    session = ClientSession()

    with aioresponses() as session_mock:
        session_mock.get(
            URL.build(
                scheme="http", host=ip_address, port=DEFAULT_HTTP_PORT, path="/shelly"
            ),
            payload=mock_response,
        )

        result = await get_info(session, ip_address, "AABBCCDDEEFF")

    await session.close()

    assert result == mock_response


@pytest.mark.asyncio
async def test_get_info_mac_mismatch() -> None:
    """Test get_info function with MAC mismatch."""
    mock_response = await load_device_fixture("shellyplus2pm", "shelly.json")
    ip_address = "10.10.10.10"

    session = ClientSession()

    with aioresponses() as session_mock:
        session_mock.get(
            URL.build(
                scheme="http", host=ip_address, port=DEFAULT_HTTP_PORT, path="/shelly"
            ),
            payload=mock_response,
        )

        with pytest.raises(
            MacAddressMismatchError,
            match="Input MAC: 112233445566, Shelly MAC: AABBCCDDEEFF",
        ):
            await get_info(session, ip_address, "112233445566")

    await session.close()


@pytest.mark.parametrize(
    ("exc", "expected_exc"),
    [
        (TimeoutError, DeviceConnectionTimeoutError),
        (ClientError, DeviceConnectionError),
        (OSError, DeviceConnectionError),
    ],
)
@pytest.mark.asyncio
async def test_get_info_exc(exc: Exception, expected_exc: Exception) -> None:
    """Test get_info function with exception."""
    ip_address = "10.10.10.10"

    session = ClientSession()

    with aioresponses() as session_mock:
        session_mock.get(
            URL.build(
                scheme="http", host=ip_address, port=DEFAULT_HTTP_PORT, path="/shelly"
            ),
            exception=exc,
        )

        with pytest.raises(expected_exc):
            await get_info(session, ip_address, "AABBCCDDEEFF")

    await session.close()


@pytest.mark.asyncio
async def test_get_info_invalid_error() -> None:
    """Test get_info function with an invalid host exception."""
    session = ClientSession()

    with pytest.raises(
        InvalidHostError, match="Host 'http://10.10.10.10' cannot contain ':'"
    ):
        await get_info(session, "http://10.10.10.10", "AABBCCDDEEFF")

    await session.close()
