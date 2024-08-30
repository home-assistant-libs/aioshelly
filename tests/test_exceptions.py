"""Tests for exceptions module."""

import pytest

from aioshelly.exceptions import DeviceConnectionError, DeviceConnectionTimeoutError


def test_device_timeout_error() -> None:
    """Test DeviceConnectionTimeoutError."""
    with pytest.raises(DeviceConnectionError):
        raise DeviceConnectionTimeoutError(
            "Ensure this inherits from DeviceConnectionError"
        )
