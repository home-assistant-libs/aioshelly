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


class ShellyLedStripEffect(TypedDict, total=False):
    """Shelly LED strip effect."""

    name: str
    controls: list[str]


class ShellyMedia(TypedDict, total=False):
    """Shelly media item from Media.List."""

    id: int
    filename: str
    preview: str
    track: int
    artist: str
    album: str
    year: int
    duration: int
    title: str
    size: int
    index: int
    type: str
    valid: bool


class ShellyRadioStation(TypedDict, total=False):
    """Shelly favourite radio station from Media.Radio.ListFavourites."""

    id: int
    name: str
    icon: str
    country_code: str


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


class ShellyWiFiSetConfig(TypedDict, total=False):
    """Shelly WiFi Set Config."""

    restart_required: bool


class ShellyWiFiNetwork(TypedDict, total=False):
    """Shelly WiFi Network from scan results."""

    ssid: str
    bssid: str
    auth: int
    channel: int
    rssi: int


class ShellyWsConfig(TypedDict, total=False):
    """Shelly Outbound Websocket Config."""

    enable: bool
    server: str | None
    ssl_ca: str


class ShellyWsSetConfig(TypedDict, total=False):
    """Shelly Outbound Websocket Set Config."""

    restart_required: bool
