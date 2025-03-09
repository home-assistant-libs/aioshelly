"""Shelly Gen2 RPC based device."""

from .device import RpcDevice, RpcUpdateType
from .utils import bluetooth_mac_from_primary_mac
from .wsrpc import WsServer

__all__ = ["RpcDevice", "RpcUpdateType", "WsServer", "bluetooth_mac_from_primary_mac"]
