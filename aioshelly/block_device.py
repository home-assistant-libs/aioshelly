"""Shelly Gen1 CoAP block based device."""
import asyncio
import logging
from typing import Dict

import aiohttp
import async_timeout

from .coap import COAP
from .common import ConnectionOptions, IpOrOptionsType, get_info, process_ip_or_options
from .const import BLOCK_DEVICE_INIT_TIMEOUT
from .exceptions import AuthRequired, NotInitialized, WrongShellyGen

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


_LOGGER = logging.getLogger(__name__)


class BlockDevice:
    """Shelly block device reppresentation."""

    def __init__(
        self,
        coap_context: COAP,
        aiohttp_session: aiohttp.ClientSession,
        options: ConnectionOptions,
    ):
        """Device init."""
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
        self.initialized = False
        self._initializing = False
        self._request_s = True

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        coap_context: COAP,
        ip_or_options: IpOrOptionsType,
        initialize: bool = True,
    ):
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        instance = cls(coap_context, aiohttp_session, options)

        if initialize:
            await instance.initialize()
        else:
            await instance.coap_request("s")

        return instance

    @property
    def ip_address(self):
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self):
        """Device initialization."""
        self._initializing = True
        self.initialized = False
        try:
            self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

            if self.options.auth or not self.requires_auth:
                await self.update_settings()
                await self.update_status()

            event_d = await self.coap_request("d")

            # We need to wait for D to come in before we request S
            # Or else we might miss the answer to D
            await event_d.wait()

            if self._request_s:
                event_s = await self.coap_request("s")
                await event_s.wait()

            self.initialized = True
        finally:
            self._initializing = False
            self._request_s = True

        if self._update_listener:
            self._update_listener(self)

    async def shutdown(self):
        """Shutdown device."""
        self._update_listener = None
        self._unsub_listening()

    async def _async_init(self):
        """Async init upon CoAP message event."""
        try:
            async with async_timeout.timeout(BLOCK_DEVICE_INIT_TIMEOUT):
                await self.initialize()
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.warning(
                "device %s initialize error - %s", self.options.ip_address, repr(err)
            )

    def _coap_message_received(self, msg):
        """COAP message received."""
        if not self._initializing and not self.initialized:
            self._request_s = False
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_init())

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

        if self._update_listener and self.initialized:
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
        if self.options.auth is None and self.requires_auth:
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

    async def trigger_ota_update(self, beta=False, url=None):
        """Trigger an ota update."""
        params = {"update": "true"}

        if url:
            params = {"url": url}
        elif beta:
            params = {"beta": "true"}

        return await self.http_request("get", "ota", params=params)

    @property
    def requires_auth(self):
        """Device check for authentication."""
        if "auth" not in self.shelly:
            raise WrongShellyGen

        return self.shelly["auth"]

    @property
    def settings(self):
        """Get device settings via HTTP."""
        if not self.initialized:
            raise NotInitialized

        if self._settings is None:
            raise AuthRequired

        return self._settings

    @property
    def status(self):
        """Get device status via HTTP."""
        if not self.initialized:
            raise NotInitialized

        if self._status is None:
            raise AuthRequired

        return self._status

    @property
    def gen(self):
        """Device generation: GEN1 - CoAP."""
        return 1

    @property
    def firmware_version(self):
        """Device firmware version."""
        if not self.initialized:
            raise NotInitialized

        return self.shelly["fw"]

    @property
    def model(self):
        """Device model."""
        if not self.initialized:
            raise NotInitialized

        return self.shelly["type"]

    @property
    def hostname(self):
        """Device hostname."""
        return self.settings["device"]["hostname"]


class Block:
    """Shelly CoAP block."""

    TYPES: dict = {}
    type = None

    def __init_subclass__(cls, blk_type, **kwargs):
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)  # type: ignore
        Block.TYPES[blk_type] = cls

    @staticmethod
    def create(device: BlockDevice, blk: dict, sensors: Dict[str, dict]):
        """Block create."""
        blk_type = blk["D"].split("_")[0]
        cls = Block.TYPES.get(blk_type, Block)
        return cls(device, blk_type, blk, sensors)

    def __init__(
        self, device: BlockDevice, blk_type: str, blk: dict, sensors: Dict[str, dict]
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
        """Get attribute."""
        if attr not in self.sensor_ids:
            raise AttributeError(f"{self.type} block has no attribute '{attr}'")

        return self.device.coap_s.get(self.sensor_ids[attr])

    def __str__(self):
        """Format string."""
        return f"<{self.type} {self.blk}>"


class LightBlock(Block, blk_type="light"):
    """Get light status."""

    async def set_state(self, **kwargs):
        """Set light state."""
        if self.device.settings["device"]["type"] == "SHRGBW2":
            path = f"{self.device.settings['mode']}/{self.channel}"
        else:
            path = f"{self.type}/{self.channel}"

        return await self.device.http_request("get", path, kwargs)
