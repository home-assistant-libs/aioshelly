"""Tests for common module."""

from unittest.mock import patch

import pytest
from aiohttp import BasicAuth

from aioshelly.common import (
    ConnectionOptions,
    is_firmware_supported,
    process_ip_or_options,
)


@pytest.mark.parametrize(
    ("gen", "model", "firmware_version", "expected"),
    [
        (4, "XYZ-G4", "20240913-112054/v1.0.0-gcb84623", False),
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
