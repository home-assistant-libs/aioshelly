"""Shelly Gen2 RPC based device."""

from .device import RpcDevice, RpcUpdateType
from .wsrpc import WsServer

__all__ = ["RpcDevice", "RpcUpdateType", "WsServer"]
