"""Shelly Gen2 RPC based device."""

from .device import RpcDevice, UpdateType
from .wsrpc import WsServer

__all__ = ["RpcDevice", "UpdateType", "WsServer"]
