"""Shelly Gen1 CoAP block based device."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from enum import Enum, auto
from http import HTTPStatus
from typing import Any, ClassVar, cast

from aiohttp import ClientResponse, ClientResponseError, ClientSession, ClientTimeout
from yarl import URL

from ..common import (
    ConnectionOptions,
    IpOrOptionsType,
    get_info,
    is_firmware_supported,
    process_ip_or_options,
)
from ..const import (
    CIT_RETRIES,
    CONNECT_ERRORS,
    DEFAULT_HTTP_PORT,
    DEVICE_IO_TIMEOUT,
    FIRMWARE_PATTERN,
    GEN1_HTTP_CIT_D_MIN_FIRMWARE_DATE,
    HTTP_CALL_TIMEOUT,
    MODEL_RGBW2,
)
from ..exceptions import (
    CustomPortNotSupported,
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    MacAddressMismatchError,
    NotInitialized,
    ShellyError,
    WrongShellyGen,
)
from ..json import json_loads
from .coap import COAP, CoapMessage, CoapType

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


HTTP_CALL_TIMEOUT_CLIENT_TIMEOUT = ClientTimeout(total=HTTP_CALL_TIMEOUT)

_LOGGER = logging.getLogger(__name__)


class BlockUpdateType(Enum):
    """Block Update type."""

    COAP_PERIODIC = auto()
    COAP_REPLY = auto()
    INITIALIZED = auto()
    ONLINE = auto()


class BlockDevice:
    """Shelly block device representation."""

    def __init__(
        self,
        coap_context: COAP,
        aiohttp_session: ClientSession,
        options: ConnectionOptions,
    ) -> None:
        """Device init."""
        self.coap_context: COAP = coap_context
        self.aiohttp_session: ClientSession = aiohttp_session
        self.options: ConnectionOptions = options
        self.coap_d: dict[str, Any] | None = None
        self.blocks: list[Block] = []
        self.coap_s: dict[str, Any] | None = None
        self._settings: dict[str, Any] | None = None
        self._shelly: dict[str, Any] | None = None
        self._status: dict[str, Any] | None = None
        sub_id = options.ip_address
        if options.device_mac:
            sub_id = options.device_mac[-6:]
        self._unsub_coap: Callable | None = coap_context.subscribe_updates(
            sub_id, self._coap_message_received
        )
        self._update_listener: Callable | None = None
        self._coap_response_events: dict[str, asyncio.Event] = {}
        self.initialized = False
        self._initializing = False
        self._last_error: ShellyError | None = None

    @classmethod
    async def create(
        cls: type[BlockDevice],
        aiohttp_session: ClientSession,
        coap_context: COAP,
        ip_or_options: IpOrOptionsType,
    ) -> BlockDevice:
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        # Try sending cit/s request to trigger a sleeping device
        try:
            await coap_context.request(options.ip_address, "s")
        except OSError as err:
            _LOGGER.debug("host %s: error: %r", options.ip_address, err)
        _LOGGER.debug(
            "host %s: block device create, MAC: %s",
            options.ip_address,
            options.device_mac,
        )
        return cls(coap_context, aiohttp_session, options)

    @property
    def ip_address(self) -> str:
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self) -> None:
        """Device initialization."""
        _LOGGER.debug("host %s: block device initialize", self.ip_address)
        if self._initializing:
            raise RuntimeError("Already initializing")

        # GEN1 cannot be configured behind a range extender as CoAP port cannot be
        # natted
        if self.options.port != DEFAULT_HTTP_PORT:
            raise CustomPortNotSupported

        self._initializing = True

        # First initialize may already have CoAP status from wakeup event
        # If device is initialized again we need to fetch new CoAP status
        if self.initialized:
            self.initialized = False
            self.coap_s = None

        ip = self.options.ip_address
        try:
            self._shelly = await get_info(
                self.aiohttp_session, self.options.ip_address, self.options.device_mac
            )

            if self.requires_auth and not self.options.auth:
                raise InvalidAuthError("auth missing and required")

            async with asyncio.timeout(DEVICE_IO_TIMEOUT):
                await self.update_settings()
                await self.update_status()

                # Older devices has incompatible CoAP protocol (v1)
                # Skip CoAP to avoid parsing errors
                if self.firmware_supported:
                    await self._update_cit_d()

                    if self.coap_s is None:
                        await self._update_cit_s()

            self.initialized = True
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                self._last_error = InvalidAuthError(err)
            else:
                self._last_error = DeviceConnectionError(err)
            _LOGGER.debug("host %s: error: %r", ip, self._last_error)
            raise self._last_error from err
        except MacAddressMismatchError as err:
            self._last_error = err
            _LOGGER.debug("host %s: error: %r", ip, err)
            raise
        except TimeoutError as err:
            self._last_error = DeviceConnectionTimeoutError(err)
            _LOGGER.debug("host %s: timeout error: %r", ip, self._last_error)
            raise self._last_error from err
        except CONNECT_ERRORS as err:
            self._last_error = DeviceConnectionError(err)
            _LOGGER.debug("host %s: error: %r", ip, self._last_error)
            raise self._last_error from err
        finally:
            self._initializing = False

        if self._update_listener:
            self._update_listener(self, BlockUpdateType.INITIALIZED)

    async def shutdown(self) -> None:
        """Shutdown device."""
        _LOGGER.debug("host %s: block device shutdown", self.ip_address)
        self._update_listener = None

        if self._unsub_coap:
            try:
                self._unsub_coap()
            except KeyError as err:
                _LOGGER.error(
                    "host %s: error during shutdown: %r", self.options.ip_address, err
                )
            self._unsub_coap = None

    def _coap_message_received(self, msg: CoapMessage) -> None:
        """COAP message received."""
        if not self._initializing and not self.initialized and self._update_listener:
            self._update_listener(self, BlockUpdateType.ONLINE)

        if not msg.payload:
            return
        if "G" in msg.payload:
            self._update_s(msg.payload, msg.coap_type)
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
        try:
            async with asyncio.timeout(DEVICE_IO_TIMEOUT):
                event = await self._coap_request("s")
                await event.wait()
        except TimeoutError as err:
            self._last_error = DeviceConnectionTimeoutError(err)
            raise self._last_error from err
        except CONNECT_ERRORS as err:
            self._last_error = DeviceConnectionError(err)
            raise self._last_error from err

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

    def _update_s(self, data: dict[str, Any], coap_type: CoapType) -> None:
        """Device update from cit/s call."""
        self.coap_s = {info[1]: info[2] for info in data["G"]}

        if self._update_listener and self.initialized:
            if coap_type is CoapType.PERIODIC:
                self._update_listener(self, BlockUpdateType.COAP_PERIODIC)
                return

            self._update_listener(self, BlockUpdateType.COAP_REPLY)

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
        self._shelly = await get_info(self.aiohttp_session, self.options.ip_address)

    async def _update_cit_d(self) -> None:
        """Update CoAP cit/d.

        cit/d via HTTP introduced in firmware 1.10
        If device does not support cit/d via HTTP,
        fallback to cit/d via CoAP request.
        """
        match = FIRMWARE_PATTERN.search(self.firmware_version)
        if match is not None and int(match[0]) >= GEN1_HTTP_CIT_D_MIN_FIRMWARE_DATE:
            cit_d_res = await self.http_request("get", "cit/d")
            self._update_d(cit_d_res)
            return

        await self._update_cit("d")

    async def _update_cit_s(self) -> None:
        """Update CoAP cit/s."""
        await self._update_cit("s")

    async def _update_cit(self, path: str) -> None:
        """Update CoAP cit with retry."""
        for retry in range(CIT_RETRIES):
            _LOGGER.debug(
                "host %s: CoAP cit/%s request (retries=%s)",
                self.ip_address,
                path,
                retry,
            )
            try:
                async with asyncio.timeout(DEVICE_IO_TIMEOUT / 4):
                    event = await self._coap_request(path)
                    await event.wait()
                    return
            except TimeoutError:
                if retry == CIT_RETRIES - 1:
                    raise

    async def _coap_request(self, path: str) -> asyncio.Event:
        """Device CoAP request."""
        if path not in self._coap_response_events:
            self._coap_response_events[path] = asyncio.Event()

        event: asyncio.Event = self._coap_response_events[path]

        await self.coap_context.request(self.ip_address, path)
        return event

    async def http_request(
        self, method: str, path: str, params: Any | None = None, retry: bool = True
    ) -> dict[str, Any]:
        """Device HTTP request."""
        if self.options.auth is None and self.requires_auth:
            raise InvalidAuthError("auth missing and required")

        host = self.options.ip_address
        _LOGGER.debug("host %s: http request: /%s (params=%s)", host, path, params)
        try:
            resp: ClientResponse = await self.aiohttp_session.request(
                method,
                URL.build(scheme="http", host=host, path=f"/{path}"),
                params=params,
                auth=self.options.auth,
                raise_for_status=True,
                timeout=HTTP_CALL_TIMEOUT_CLIENT_TIMEOUT,
            )
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                self._last_error = InvalidAuthError(err)
                raise InvalidAuthError(err) from err

            self._last_error = DeviceConnectionError(err)
            raise self._last_error from err
        except TimeoutError as err:
            self._last_error = DeviceConnectionTimeoutError(err)
            if retry:
                _LOGGER.debug(
                    "host %s: http request timeout: %r", host, self._last_error
                )
                return await self.http_request(method, path, params, retry=False)

            _LOGGER.debug(
                "host %s: http request retry timeout: %r", host, self._last_error
            )
            raise self._last_error from err
        except CONNECT_ERRORS as err:
            self._last_error = DeviceConnectionError(err)
            if retry:
                _LOGGER.debug("host %s: http request error: %r", host, self._last_error)
                return await self.http_request(method, path, params, retry=False)

            _LOGGER.debug(
                "host %s: http request retry error: %r", host, self._last_error
            )
            raise self._last_error from err

        resp_json = await resp.json(loads=json_loads)
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

    async def set_thermostat_state(self, channel: int = 0, **kwargs: Any) -> None:
        """Set thermostat state (Shelly TRV)."""
        await self.http_request("get", f"thermostat/{channel}", kwargs)

    @property
    def requires_auth(self) -> bool:
        """Device check for authentication."""
        if "auth" not in self.shelly:
            raise WrongShellyGen

        return bool(self.shelly["auth"])

    @property
    def settings(self) -> dict[str, Any]:
        """Get device settings via HTTP."""
        if not self.initialized:
            raise NotInitialized

        if self._settings is None:
            raise InvalidAuthError

        return self._settings

    @property
    def status(self) -> dict[str, Any]:
        """Get device status via HTTP."""
        if not self.initialized:
            raise NotInitialized

        if self._status is None:
            raise InvalidAuthError

        return self._status

    @property
    def shelly(self) -> dict[str, Any]:
        """Device firmware version."""
        if self._shelly is None:
            raise NotInitialized

        return self._shelly

    @property
    def gen(self) -> int:
        """Device generation: GEN1 - CoAP."""
        return 1

    @property
    def firmware_version(self) -> str:
        """Device firmware version."""
        return cast(str, self.shelly["fw"])

    @property
    def model(self) -> str:
        """Device model."""
        return cast(str, self.shelly["type"])

    @property
    def hostname(self) -> str:
        """Device hostname."""
        return cast(str, self.settings["device"]["hostname"])

    @property
    def name(self) -> str:
        """Device name."""
        return cast(str, self.settings["name"] or self.hostname)

    @property
    def last_error(self) -> ShellyError | None:
        """Return the last error during async device init."""
        return self._last_error

    @property
    def firmware_supported(self) -> bool:
        """Return True if device firmware version is supported."""
        return is_firmware_supported(self.gen, self.model, self.firmware_version)


class Block:
    """Shelly CoAP block."""

    TYPES: ClassVar[dict] = {}
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
    ) -> None:
        """Block initialize."""
        self.type = blk_type
        self.device = device
        self.blk = blk
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
            msg = (
                f"Device {self.device.model} with firmware "
                f"{self.device.firmware_version} has no attribute '{attr}' "
                f"in block {self.type}"
            )
            raise AttributeError(msg)

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
        if self.device.settings["device"]["type"] == MODEL_RGBW2:
            path = f"{self.device.settings['mode']}/{self.channel}"
        else:
            path = f"{self.type}/{self.channel}"

        return await self.device.http_request("get", path, kwargs)
