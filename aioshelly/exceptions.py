"""Shelly exceptions."""
from __future__ import annotations

# Internal or run time errors:
#    Errors not needed to be handled by the caller
#    'NotInitialized' & 'WrongShellyGen' indicate runtime errors


class ShellyError(Exception):
    """Base class for aioshelly errors."""


class ConnectionClosed(ShellyError):
    """Exception raised when the connection is closed."""


class InvalidMessage(ShellyError):
    """Exception raised when an invalid message is received."""


class NotInitialized(ShellyError):
    """Raised if device is not initialized."""


class WrongShellyGen(ShellyError):
    """Exception raised to indicate wrong Shelly generation."""


# Errors to be handled by the caller:
#    Errors that are expected to happen and should be handled by the caller.


class DeviceConnectionError(ShellyError):
    """Exception indicates device connection errors."""


class FirmwareUnsupported(ShellyError):
    """Raised if device firmware version is unsupported."""


class InvalidAuthError(ShellyError):
    """Raised to indicate invalid or missing authentication error."""


class MacAddressMismatchError(ShellyError):
    """Raised if input MAC address does not match the device MAC address."""


class RpcCallError(ShellyError):
    """Raised to indicate errors in RPC call."""

    def __init__(self, code: int, message: str = ""):
        """Initialize JSON RPC errors."""
        self.code = code
        self.message = message
        super().__init__(code, message)
