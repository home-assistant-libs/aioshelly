"""Shelly Gen1 CoAP block based device."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, cast

import aiohttp
import async_timeout
from aiohttp.client_reqrep import ClientResponse

from .coap import COAP, CoapMessage
from .common import ConnectionOptions, IpOrOptionsType, get_info, process_ip_or_options
from .const import BLOCK_DEVICE_INIT_TIMEOUT, HTTP_CALL_TIMEOUT
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
        self.coap_context: COAP = coap_context
        self.aiohttp_session: aiohttp.ClientSession = aiohttp_session
        self.options: ConnectionOptions = options
        self.coap_d: dict[str, Any] | None = None
        self.blocks: list | None = None
        self.coap_s: dict[str, Any] | None = None
        self._settings: dict[str, Any] | None = None
        self.shelly: dict[str, Any] | None = None
        self._status: dict[str, Any] | None = None
        self._unsub_listening = coap_context.subscribe_updates(
            options.ip_address, self._coap_message_received
        )
        self._update_listener: Callable | None = None
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
    ) -> BlockDevice:
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        instance = cls(coap_context, aiohttp_session, options)

        if initialize:
            await instance.initialize()
        else:
            await instance.coap_request("s")

        return instance

    @property
    def ip_address(self) -> str:
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self) -> None:
        """Device initialization."""
        self._initializing = True
        self.initialized = False
        try:
            await self.update_shelly()

            if self.options.auth or not self.requires_auth:
                await self.update_settings()
                await self.update_status()

            event_d: asyncio.Event = await self.coap_request("d")

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

    def shutdown(self) -> None:
        """Shutdown device."""
        self._update_listener = None
        self._unsub_listening()

    async def _async_init(self) -> None:
        """Async init upon CoAP message event."""
        try:
            async with async_timeout.timeout(BLOCK_DEVICE_INIT_TIMEOUT):
                await self.initialize()
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.warning(
                "device %s initialize error - %s", self.options.ip_address, repr(err)
            )

    def _coap_message_received(self, msg: CoapMessage) -> None:
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

    async def update(self) -> None:
        """Device update."""
        event = await self.coap_request("s")
        await event.wait()

    def _update_d(self, data: dict[str, Any]) -> None:
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

    def _update_s(self, data: dict[str, Any]) -> None:
        """Device update from cit/s call."""
        self.coap_s = {info[1]: info[2] for info in data["G"]}

        if self._update_listener and self.initialized:
            self._update_listener(self)

    def subscribe_updates(self, update_listener: Callable) -> None:
        """Subscribe to device status updates."""
        self._update_listener = update_listener

    async def update_status(self) -> None:
        """Device update from /status (HTTP)."""
        self._status = await self.http_request("get", "status")

    async def update_settings(self) -> None:
        """Device update from /settings (HTTP)."""
        self._settings = await self.http_request("get", "settings")

    async def update_shelly(self) -> None:
        """Device update for /shelly (HTTP)."""
        self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

    async def coap_request(self, path: str) -> asyncio.Event:
        """Device CoAP request."""
        if path not in self._coap_response_events:
            self._coap_response_events[path] = asyncio.Event()

        event: asyncio.Event = self._coap_response_events[path]

        await self.coap_context.request(self.ip_address, path)
        return event

    async def http_request(
        self, method: str, path: str, params: Any | None = None
    ) -> dict[str, Any]:
        """Device HTTP request."""
        if self.options.auth is None and self.requires_auth:
            raise AuthRequired

        _LOGGER.debug("aiohttp request: /%s (params=%s)", path, params)
        resp: ClientResponse = await self.aiohttp_session.request(
            method,
            f"http://{self.options.ip_address}/{path}",
            params=params,
            auth=self.options.auth,
            raise_for_status=True,
            timeout=HTTP_CALL_TIMEOUT,
        )
        resp_json = await resp.json()
        _LOGGER.debug("aiohttp response: %s", resp_json)
        return cast(dict, resp_json)

    async def switch_light_mode(self, mode: str) -> dict[str, Any]:
        """Change device mode color/white."""
        return await self.http_request("get", "settings", {"mode": mode})

    async def trigger_ota_update(
        self, beta: bool = False, url: str | None = None
    ) -> dict[str, Any]:
        """Trigger an ota update."""
        params = {"update": "true"}

        if url:
            params = {"url": url}
        elif beta:
            params = {"beta": "true"}

        return await self.http_request("get", "ota", params=params)

    async def trigger_reboot(self) -> None:
        """Trigger a device reboot."""
        await self.http_request("get", "reboot")

    async def trigger_shelly_gas_self_test(self) -> None:
        """Trigger a Shelly Gas self test."""
        await self.http_request("get", "self_test")

    async def trigger_shelly_gas_mute(self) -> None:
        """Trigger a Shelly Gas mute action."""
        await self.http_request("get", "mute")

    async def trigger_shelly_gas_unmute(self) -> None:
        """Trigger a Shelly Gas unmute action."""
        await self.http_request("get", "unmute")

    async def set_shelly_motion_detection(self, enable: bool) -> None:
        """Enable or disable Shelly Motion motion detection."""
        params = {"motion_enable": "true"} if enable else {"motion_enable": "false"}

        await self.http_request("get", "settings", params)

    @property
    def requires_auth(self) -> bool:
        """Device check for authentication."""
        assert self.shelly

        if "auth" not in self.shelly:
            raise WrongShellyGen

        return bool(self.shelly["auth"])

    @property
    def settings(self) -> dict[str, Any]:
        """Get device settings via HTTP."""
        if not self.initialized:
            raise NotInitialized

        if self._settings is None:
            raise AuthRequired

        return self._settings

    @property
    def status(self) -> dict[str, Any]:
        """Get device status via HTTP."""
        if not self.initialized:
            raise NotInitialized

        if self._status is None:
            raise AuthRequired

        return self._status

    @property
    def gen(self) -> int:
        """Device generation: GEN1 - CoAP."""
        return 1

    @property
    def firmware_version(self) -> str:
        """Device firmware version."""
        if not self.initialized:
            raise NotInitialized

        assert self.shelly

        return cast(str, self.shelly["fw"])

    @property
    def model(self) -> str:
        """Device model."""
        if not self.initialized:
            raise NotInitialized

        assert self.shelly

        return cast(str, self.shelly["type"])

    @property
    def hostname(self) -> str:
        """Device hostname."""
        return cast(str, self.settings["device"]["hostname"])


class Block:
    """Shelly CoAP block."""

    TYPES: dict = {}
    type = None

    def __init_subclass__(cls, blk_type: str = "", **kwargs: Any) -> None:
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)
        Block.TYPES[blk_type] = cls

    @staticmethod
    def create(device: BlockDevice, blk: dict, sensors: dict[str, dict]) -> Any:
        """Block create."""
        blk_type = blk["D"].split("_")[0]
        cls = Block.TYPES.get(blk_type, Block)
        return cls(device, blk_type, blk, sensors)

    def __init__(
        self, device: BlockDevice, blk_type: str, blk: dict, sensors: dict[str, dict]
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
    def index(self) -> str:
        """Block index."""
        return cast(str, self.blk["I"])

    @property
    def description(self) -> str:
        """Block description."""
        return cast(str, self.blk["D"])

    @property
    def channel(self) -> str | None:
        """Block description for channel."""
        return self.description.split("_")[1] if "_" in self.description else None

    def info(self, attr: str) -> dict[str, Any]:
        """Return info over attribute."""
        return self.sensors[self.sensor_ids[attr]]

    def current_values(self) -> dict[str, Any]:
        """Block values."""
        if self.device.coap_s is None:
            return {}

        return {
            desc: self.device.coap_s.get(index)
            for desc, index in self.sensor_ids.items()
        }

    async def set_state(self, **kwargs: Any) -> dict[str, Any]:
        """Set state request (HTTP)."""
        return await self.device.http_request(
            "get", f"{self.type}/{self.channel}", kwargs
        )

    async def toggle(self) -> dict[str, Any]:
        """Toggle status."""
        return await self.set_state(turn="off" if self.output else "on")

    def __getattr__(self, attr: str) -> str | None:
        """Get attribute."""
        if attr not in self.sensor_ids:
            raise AttributeError(
                f"Device {self.device.model} with firmware {self.device.firmware_version} has no attribute '{attr}' in block {self.type}"
            )

        if self.device.coap_s is None:
            return None

        return self.device.coap_s.get(self.sensor_ids[attr])

    def __str__(self) -> str:
        """Format string."""
        return f"<{self.type} {self.blk}>"


class LightBlock(Block, blk_type="light"):
    """Get light status."""

    async def set_state(self, **kwargs: Any) -> dict[str, Any]:
        """Set light state."""
        if self.device.settings["device"]["type"] == "SHRGBW2":
            path = f"{self.device.settings['mode']}/{self.channel}"
        else:
            path = f"{self.type}/{self.channel}"

        return await self.device.http_request("get", path, kwargs)
