"""Tests for common module."""

import pytest

from aioshelly.common import is_firmware_supported


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
