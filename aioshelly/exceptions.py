"""Shelly exceptions."""
from __future__ import annotations


class ShellyError(Exception):
    """Base class for aioshelly errors."""


class AuthRequired(ShellyError):
    """Raised during initialization if auth is required but not given."""


class NotInitialized(ShellyError):
    """Raised if device is not initialized."""


class FirmwareUnsupported(ShellyError):
    """Raised if device firmware version is unsupported."""


class CannotConnect(ShellyError):
    """Exception raised when failed to connect the client."""


class ConnectionFailed(ShellyError):
    """Exception raised when a connection failed."""


class ConnectionClosed(ShellyError):
    """Exception raised when the connection is closed."""


class InvalidMessage(ShellyError):
    """Exception raised when an invalid message is received."""


class RPCError(ShellyError):
    """Base class for RPC errors."""


class RPCTimeout(RPCError):
    """Raised upon RPC call timeout."""


class JSONRPCError(RPCError):
    """Raised during RPC JSON parsing errors."""

    def __init__(self, code: int, message: str = ""):
        """Initialize JSON RPC errors."""
        self.code = code
        self.message = message
        super().__init__(code, message)


class InvalidAuthError(JSONRPCError):
    """Raised to indicate invalid authentication error."""


class WrongShellyGen(ShellyError):
    """Exception raised to indicate wrong Shelly generation."""
