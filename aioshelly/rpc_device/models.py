"""Shelly Gen2 RPC based device models."""

from __future__ import annotations

from typing import TypedDict


class ShellyScript(TypedDict, total=False):
    """Shelly Script."""

    id: int
    name: str
    enable: bool
    running: bool


class ShellyScriptCode(TypedDict, total=False):
    """Shelly Script Code."""

    data: str


class ShellyBLERpcConfig(TypedDict, total=False):
    """Shelly BLE RPC Config."""

    enable: bool


class ShellyBLEConfig(TypedDict, total=False):
    """Shelly BLE Config."""

    enable: bool
    rpc: ShellyBLERpcConfig


class ShellyBLESetConfig(TypedDict, total=False):
    """Shelly BLE Set Config."""

    restart_required: bool


class ShellyWsConfig(TypedDict, total=False):
    """Shelly Outbound Websocket Config."""

    enable: bool
    server: str | None
    ssl_ca: str


class ShellyWsSetConfig(TypedDict, total=False):
    """Shelly Outbound Websocket Set Config."""

    restart_required: bool
