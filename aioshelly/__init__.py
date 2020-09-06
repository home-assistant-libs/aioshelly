from dataclasses import dataclass
import json
from typing import Dict, Optional, Union

import aiohttp
import aiocoap


MODEL_NAMES = {
    "SH2LED-1": "Shelly 2LED",
    "SHAIR-1": "Shelly Air",
    "SHBDUO-1": "Shelly DUO",
    "SHBLB-1": "Shelly Bulb",
    "SHBTN-1": "Shelly Button1",
    "SHBVIN-1": "Shelly Vintage",
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
    "SHSW-PM": "Shelly 1PM",
    "SHUNI-1": "Shelly UNI",
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


class ShellyError(Exception):
    """Base class for aioshelly errors."""


class AuthRequired(ShellyError):
    """Raised during initialization if auth is required but not given."""


@dataclass(frozen=True)
class ConnectionOptions:
    ip: str
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


async def get_info(aiohttp_session: aiohttp.ClientSession, ip):
    async with aiohttp_session.get(
        f"http://{ip}/shelly", raise_for_status=True
    ) as resp:
        return await resp.json()


class Device:
    def __init__(
        self,
        coap_context: aiocoap.Context,
        aiohttp_session: aiohttp.ClientSession,
        options: ConnectionOptions,
    ):
        self.coap_context = coap_context
        self.aiohttp_session = aiohttp_session
        self.options = options
        self.d = None
        self.blocks = None
        self.s = None
        self._settings = None
        self.shelly = None

    @classmethod
    async def create(
        cls, aiohttp_session, ip_or_options: Union[str, ConnectionOptions]
    ):
        if isinstance(ip_or_options, str):
            options = ConnectionOptions(ip_or_options)
        else:
            options = ip_or_options

        coap_context = await aiocoap.Context.create_client_context()
        instance = cls(coap_context, aiohttp_session, options)

        try:
            await instance.initialize()
        except Exception:
            await coap_context.shutdown()
            raise

        return instance

    @property
    def ip(self):
        return self.options.ip

    async def initialize(self):
        self.shelly = await get_info(self.aiohttp_session, self.options.ip)

        self.d = await self.coap_request("d")
        blocks = []

        for blk in self.d["blk"]:
            blk_index = blk["I"]
            blk_sensors = {
                val["I"]: val
                for val in self.d["sen"]
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

        await self.update()

        if self.options.auth or not self.shelly["auth"]:
            self._settings = await self.http_request("get", "settings")

    async def update(self):
        self.s = {info[1]: info[2] for info in (await self.coap_request("s"))["G"]}

    async def coap_request(self, path):
        request = aiocoap.Message(
            code=aiocoap.GET, uri=f"coap://{self.options.ip}/cit/{path}"
        )
        response = await self.coap_context.request(request).response
        return json.loads(response.payload)

    async def http_request(self, method, path, params=None):
        if self.read_only:
            raise AuthRequired

        resp = await self.aiohttp_session.request(
            method,
            f"http://{self.options.ip}/{path}",
            params=params,
            auth=self.options.auth,
            raise_for_status=True,
        )
        return await resp.json()

    async def shutdown(self):
        await self.coap_context.shutdown()

    @property
    def requires_auth(self):
        return self.shelly["auth"]

    @property
    def read_only(self):
        return self.options.auth is None and self.requires_auth

    @property
    def settings(self):
        if self._settings is None:
            raise AuthRequired

        return self._settings


class Block:
    TYPES = {}
    type = None

    def __init_subclass__(cls, blk_type, **kwargs):
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)  # type: ignore
        Block.TYPES[blk_type] = cls

    @staticmethod
    def create(device: Device, blk: dict, sensors: Dict[str, dict]):
        blk_type = blk["D"].split("_")[0]
        cls = Block.TYPES.get(blk_type, Block)
        return cls(device, blk_type, blk, sensors)

    def __init__(
        self, device: Device, blk_type: str, blk: dict, sensors: Dict[str, dict]
    ):
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
        return self.blk["I"]

    @property
    def description(self):
        return self.blk["D"]

    @property
    def channel(self):
        return self.description.split("_")[1]

    def info(self, attr):
        """Return info over attribute."""
        return self.sensors[self.sensor_ids[attr]]

    def current_values(self):
        return {
            desc: self.device.s.get(index) for desc, index in self.sensor_ids.items()
        }

    async def set_state(self, **kwargs):
        return await self.device.http_request(
            "get", f"{self.type}/{self.channel}", kwargs
        )

    async def toggle(self):
        return await self.set_state(turn="off" if self.output else "on")

    def __getattr__(self, attr):
        if attr not in self.sensor_ids:
            raise AttributeError(f"{self.type} block has no attribute '{attr}'")

        return self.device.s.get(self.sensor_ids[attr])

    def __str__(self):
        return f"<{self.type} {self.blk}>"


class RelayBlock(Block, blk_type="relay"):
    async def turn_on(self):
        return await self.set_state(turn="on")

    async def turn_off(self):
        return await self.set_state(turn="off")
