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


class ShellyWiFiSetConfig(TypedDict, total=False):
    """Shelly WiFi Set Config."""

    restart_required: bool


class ShellyCoverMotor(TypedDict, total=False):
    """Shelly Cover Motor Config."""

    idle_power_thr: float
    idle_confirm_period: float


class ShellyCoverObstructionDetection(TypedDict, total=False):
    """Shelly Cover Obstruction Detection Config."""

    enable: bool
    direction: str
    action: str
    power_thr: float
    holdoff: float


class ShellyCoverSafetySwitch(TypedDict, total=False):
    """Shelly Cover Safety Switch Config."""

    enable: bool
    direction: str
    action: str
    allowed_move: str | None


class ShellyCoverSlat(TypedDict, total=False):
    """Shelly Cover Slat Config."""

    enable: bool
    open_time: float
    close_time: float
    step: int
    retain_pos: bool
    precise_ctl: bool


class ShellyCoverConfig(TypedDict, total=False):
    """Shelly Cover Config, accepted by Cover.SetConfig."""

    name: str | None
    motor: ShellyCoverMotor
    maxtime_open: float
    maxtime_close: float
    initial_state: str
    invert_directions: bool
    maintenance_mode: bool
    in_mode: str
    in_locked: bool
    swap_inputs: bool
    safety_switch: ShellyCoverSafetySwitch
    power_limit: float | None
    voltage_limit: float | None
    undervoltage_limit: float | None
    current_limit: float | None
    obstruction_detection: ShellyCoverObstructionDetection
    slat: ShellyCoverSlat


class ShellyCoverSetConfig(TypedDict, total=False):
    """Shelly Cover Set Config."""

    restart_required: bool


class ShellySwitchCounts(TypedDict, total=False):
    """Shelly Switch Counters Config."""

    enable: bool
    power_thr: float


class ShellySwitchConfig(TypedDict, total=False):
    """Shelly Switch Config, accepted by Switch.SetConfig."""

    name: str | None
    in_mode: str
    in_locked: bool
    initial_state: str
    auto_on: bool
    auto_on_delay: float
    auto_off: bool
    auto_off_delay: float
    autorecover_voltage_errors: bool
    input_id: int
    power_limit: float | None
    voltage_limit: float | None
    undervoltage_limit: float | None
    current_limit: float | None
    reverse: bool
    counts: ShellySwitchCounts


class ShellySwitchSetConfig(TypedDict, total=False):
    """Shelly Switch Set Config."""

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
