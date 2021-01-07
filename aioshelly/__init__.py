"""Shelly CoAP library."""
import asyncio
import ipaddress
import re
from dataclasses import dataclass
from socket import gethostbyname
from typing import Dict, Optional, Union

import aiohttp

from .coap import COAP

MODEL_NAMES = {
    "SH2LED-1": "Shelly 2LED",
    "SHAIR-1": "Shelly Air",
    "SHBDUO-1": "Shelly DUO",
    "SHBLB-1": "Shelly Bulb",
    "SHBTN-1": "Shelly Button1",
    "SHBTN-2": "Shelly Button1",  # hw v2
    "SHBVIN-1": "Shelly Vintage",
    "SHCB-1": "Shelly Bulb RGBW",
    "SHCL-255": "Shelly Color",
    "SHDIMW-1": "Shelly Dimmer W1",
    "SHDM-1": "Shelly Dimmer",
    "SHDM-2": "Shelly Dimmer 2",
    "SHDW-1": "Shelly Door/Window",
    "SHDW-2": "Shelly Door/Window 2",
    "SHEM": "Shelly EM",
    "SHEM-3": "Shelly 3EM",
    "SHGS-1": "Shelly Gas",
    "SHHT-1": "Shelly H&T",
    "SHIX3-1": "Shelly i3",
    "SHMOS-01": "Shelly Motion",
    "SHPLG-1": "Shelly Plug",
    "SHPLG-S": "Shelly Plug S",
    "SHPLG-U1": "Shelly Plug US",
    "SHPLG2-1": "Shelly Plug E",
    "SHRGBW2": "Shelly RGBW2",
    "SHRGBWW-01": "Shelly RGBW",
    "SHSEN-1": "Shelly Sense",
    "SHSM-01": "Shelly Smoke",
    "SHSM-02": "Shelly Smoke 2",
    "SHSPOT-1": "Shelly Spot",
    "SHSPOT-2": "Shelly Spot 2",
    "SHSW-1": "Shelly 1",
    "SHSW-21": "Shelly 2",
    "SHSW-25": "Shelly 2.5",
    "SHSW-44": "Shelly 4Pro",
    "SHSW-L": "Shelly 1L",
    "SHSW-PM": "Shelly 1PM",
    "SHUNI-1": "Shelly UNI",
    "SHVIN-1": "Shelly Vintage",
    "SHWT-1": "Shelly Flood",
}

BLOCK_VALUE_UNIT = "U"
BLOCK_VALUE_TYPE = "T"

BLOCK_VALUE_TYPE_ALARM = "A"
BLOCK_VALUE_TYPE_BATTERY_LEVEL = "B"
BLOCK_VALUE_TYPE_CONCENTRATION = "C"
BLOCK_VALUE_TYPE_ENERGY = "E"
BLOCK_VALUE_TYPE_EVENT = "EV"
BLOCK_VALUE_TYPE_EVENT_COUNTER = "EVC"
BLOCK_VALUE_TYPE_HUMIDITY = "H"
BLOCK_VALUE_TYPE_CURRENT = "I"
BLOCK_VALUE_TYPE_LUMINOSITY = "L"
BLOCK_VALUE_TYPE_POWER = "P"
BLOCK_VALUE_TYPE_STATUS = "S"  # (catch-all if no other fits)
BLOCK_VALUE_TYPE_TEMPERATURE = "T"
BLOCK_VALUE_TYPE_VOLTAGE = "V"

# Firmware 1.8.0 release date
MIN_FIRMWARE_DATE = 20200812
FIRMWARE_PATTERN = re.compile(r"^(\d{8})")


class ShellyError(Exception):
    """Base class for aioshelly errors."""


class AuthRequired(ShellyError):
    """Raised during initialization if auth is required but not given."""


class FirmwareUnsupported(ShellyError):
    """Raised if device firmware version is unsupported."""


@dataclass
class ConnectionOptions:
    """Shelly options for connection."""

    ip_address: str
    username: Optional[str] = None
    password: Optional[str] = None
    temperature_unit: str = "C"
    auth: Optional[aiohttp.BasicAuth] = None

    def __post_init__(self):
        """Called after initialization."""
        if self.username is not None:
            if self.password is None:
                raise ValueError("Supply both username and password")

            object.__setattr__(
                self, "auth", aiohttp.BasicAuth(self.username, self.password)
            )


async def get_info(aiohttp_session: aiohttp.ClientSession, ip_address):
    """Get info from device trough REST call."""
    async with aiohttp_session.get(
        f"http://{ip_address}/shelly", raise_for_status=True
    ) as resp:
        result = await resp.json()

    if not supported_firmware(result["fw"]):
        raise FirmwareUnsupported

    return result


def supported_firmware(ver_str: str):
    """Return True if device firmware version is supported."""
    match = FIRMWARE_PATTERN.search(ver_str)

    if match is None:
        return False

    # We compare firmware release dates because Shelly version numbering is
    # inconsistent, sometimes the word is used as the version number.
    return int(match[0]) >= MIN_FIRMWARE_DATE


class Device:
    """Shelly device reppresentation."""

    def __init__(
        self,
        coap_context: COAP,
        aiohttp_session: aiohttp.ClientSession,
        options: ConnectionOptions,
    ):
        self.coap_context = coap_context
        self.aiohttp_session = aiohttp_session
        self.options = options
        self.coap_d = None
        self.blocks = None
        self.coap_s = None
        self._settings = None
        self.shelly = None
        self._status = None
        self._unsub_listening = coap_context.subscribe_updates(
            options.ip_address, self._coap_message_received
        )
        self._update_listener = None
        self._coap_response_events: dict = {}

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        coap_context: COAP,
        ip_or_options: Union[str, ConnectionOptions],
    ):
        """Device creation."""
        if isinstance(ip_or_options, str):
            options = ConnectionOptions(ip_or_options)
        else:
            options = ip_or_options

        try:
            ipaddress.ip_address(options.ip_address)
        except ValueError:
            loop = asyncio.get_running_loop()
            options.ip_address = await loop.run_in_executor(
                None, gethostbyname, options.ip_address
            )

        instance = cls(coap_context, aiohttp_session, options)
        await instance.initialize()
        return instance

    @property
    def ip_address(self):
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self):
        """Device initialization."""
        self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

        event_d = await self.coap_request("d")

        # We need to wait for D to come in before we request S
        # Or else we might miss the answer to D
        await event_d.wait()

        event_s = await self.coap_request("s")

        if self.options.auth or not self.shelly["auth"]:
            await self.update_settings()
            await self.update_status()

        await event_s.wait()

    def shutdown(self):
        """Shutdown device."""
        self._update_listener = None
        self._unsub_listening()

    def _coap_message_received(self, msg):
        """CoAP message received."""
        if not msg.payload:
            return
        if "G" in msg.payload:
            self._update_s(msg.payload)
            path = "s"
        elif "blk" in msg.payload:
            self._update_d(msg.payload)
            path = "d"
        else:
            # Unknown msg
            return

        event = self._coap_response_events.pop(path, None)
        if event is not None:
            event.set()

    async def update(self):
        """Device update."""
        event = await self.coap_request("s")
        await event.wait()

    def _update_d(self, data):
        """Device update from cit/d call."""
        self.coap_d = data
        blocks = []

        for blk in self.coap_d["blk"]:
            blk_index = blk["I"]
            blk_sensors = {
                val["I"]: val
                for val in self.coap_d["sen"]
                if (
                    val["L"] == blk_index
                    if isinstance(val["L"], int)
                    else blk_index in val["L"]
                )
            }
            block = Block.create(self, blk, blk_sensors)

            if block:
                blocks.append(block)

        self.blocks = blocks

    def _update_s(self, data):
        """Device update from cit/s call."""
        self.coap_s = {info[1]: info[2] for info in data["G"]}

        if self._update_listener:
            self._update_listener(self)

    def subscribe_updates(self, update_listener):
        """Subscribe to device status updates."""
        self._update_listener = update_listener

    async def update_status(self):
        """Device update from /status (HTTP)."""
        self._status = await self.http_request("get", "status")

    async def update_settings(self):
        """Device update from /settings (HTTP)."""
        self._settings = await self.http_request("get", "settings")

    async def coap_request(self, path):
        """Device CoAP request."""
        if path not in self._coap_response_events:
            self._coap_response_events[path] = asyncio.Event()

        event = self._coap_response_events[path]

        await self.coap_context.request(self.ip_address, path)
        return event

    async def http_request(self, method, path, params=None):
        """Device HTTP request."""
        if self.read_only:
            raise AuthRequired

        resp = await self.aiohttp_session.request(
            method,
            f"http://{self.options.ip_address}/{path}",
            params=params,
            auth=self.options.auth,
            raise_for_status=True,
        )
        return await resp.json()

    async def switch_light_mode(self, mode):
        """Change device mode color/white."""
        return await self.http_request("get", "settings", {"mode": mode})

    @property
    def requires_auth(self):
        """Device check for authentication."""
        return self.shelly["auth"]

    @property
    def read_only(self):
        """Device check if can only read data."""
        return self.options.auth is None and self.requires_auth

    @property
    def settings(self):
        """Device get settings (HTTP)."""
        if self._settings is None:
            raise AuthRequired

        return self._settings

    @property
    def status(self):
        """Device get status (HTTP)."""
        if self._status is None:
            raise AuthRequired

        return self._status


class Block:
    """Shelly CoAP block."""

    TYPES: dict = {}
    type = None

    def __init_subclass__(cls, blk_type, **kwargs):
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)  # type: ignore
        Block.TYPES[blk_type] = cls

    @staticmethod
    def create(device: Device, blk: dict, sensors: Dict[str, dict]):
        """Block create."""
        blk_type = blk["D"].split("_")[0]
        cls = Block.TYPES.get(blk_type, Block)
        return cls(device, blk_type, blk, sensors)

    def __init__(
        self, device: Device, blk_type: str, blk: dict, sensors: Dict[str, dict]
    ):
        """Block initialize."""
        self.type = blk_type
        self.device = device
        # https://shelly-api-docs.shelly.cloud/#coiot-device-description-cit-d
        # blk
        # {
        #     "I": id,
        #     "D": description
        # }
        self.blk = blk
        # Sensors:
        # {
        #     "I": id,
        #     "T": type,
        #     "D": description,
        #     "U": unit,
        #     "R": range,
        #     "L": links
        # }
        self.sensors = sensors
        sensor_ids = {}
        for sensor in sensors.values():
            if sensor["D"] not in sensor_ids:
                sensor_ids[sensor["D"]] = sensor["I"]
                continue

            if sensor[BLOCK_VALUE_TYPE] != BLOCK_VALUE_TYPE_TEMPERATURE:
                raise ValueError(
                    "Found duplicate description for non-temperature sensor"
                )

            if sensor[BLOCK_VALUE_UNIT] == device.options.temperature_unit:
                sensor_ids[sensor["D"]] = sensor["I"]

        self.sensor_ids = sensor_ids

    @property
    def index(self):
        """Block index."""
        return self.blk["I"]

    @property
    def description(self):
        """Block description."""
        return self.blk["D"]

    @property
    def channel(self):
        """Block description for channel."""
        return self.description.split("_")[1] if "_" in self.description else None

    def info(self, attr):
        """Return info over attribute."""
        return self.sensors[self.sensor_ids[attr]]

    def current_values(self):
        """Block values."""
        return {
            desc: self.device.coap_s.get(index)
            for desc, index in self.sensor_ids.items()
        }

    async def set_state(self, **kwargs):
        """Set state request (HTTP)."""
        return await self.device.http_request(
            "get", f"{self.type}/{self.channel}", kwargs
        )

    async def toggle(self):
        """Toggle status."""
        return await self.set_state(turn="off" if self.output else "on")

    def __getattr__(self, attr):
        if attr not in self.sensor_ids:
            raise AttributeError(f"{self.type} block has no attribute '{attr}'")

        return self.device.coap_s.get(self.sensor_ids[attr])

    def __str__(self):
        return f"<{self.type} {self.blk}>"


class LightBlock(Block, blk_type="light"):
    """Get light status."""

    async def set_state(self, **kwargs):
        if self.device.settings["device"]["type"] == "SHRGBW2":
            path = f"{self.device.settings['mode']}/{self.channel}"
        else:
            path = f"{self.type}/{self.channel}"

        return await self.device.http_request("get", path, kwargs)
