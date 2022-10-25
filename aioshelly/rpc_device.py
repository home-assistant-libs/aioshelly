"""Shelly Gen2 RPC based device."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, cast

import aiohttp
import async_timeout
from aiohttp.client import ClientSession

from .common import ConnectionOptions, IpOrOptionsType, get_info, process_ip_or_options
from .const import CONNECT_ERRORS, DEVICE_IO_TIMEOUT
from .exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    NotInitialized,
    RpcCallError,
    ShellyError,
    WrongShellyGen,
)
from .wsrpc import WsRPC, WsServer

_LOGGER = logging.getLogger(__name__)


def mergedicts(dict1: dict, dict2: dict) -> dict:
    """Deep dicts merge."""
    result = dict(dict1)
    result.update(dict2)
    for key, value in result.items():
        if isinstance(value, dict) and isinstance(dict1.get(key), dict):
            result[key] = mergedicts(dict1[key], value)
    return result


class RpcDevice:
    """Shelly RPC device representation."""

    def __init__(
        self,
        ws_context: WsServer,
        aiohttp_session: aiohttp.ClientSession,
        options: ConnectionOptions,
    ):
        """Device init."""
        self.aiohttp_session: ClientSession = aiohttp_session
        self.options: ConnectionOptions = options
        self.shelly: dict[str, Any] | None = None
        self._status: dict[str, Any] | None = None
        self._event: dict[str, Any] | None = None
        self._config: dict[str, Any] | None = None
        self._wsrpc = WsRPC(options.ip_address, self._on_notification)
        self._unsub_ws: Callable | None = ws_context.subscribe_updates(
            options.ip_address, self._wsrpc.handle_frame
        )
        self._update_listener: Callable | None = None
        self.initialized: bool = False
        self._initializing: bool = False
        self._last_error: ShellyError | None = None

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        ws_context: WsServer,
        ip_or_options: IpOrOptionsType,
        initialize: bool = True,
    ) -> RpcDevice:
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        instance = cls(ws_context, aiohttp_session, options)

        if initialize:
            await instance.initialize()

        return instance

    async def _async_init(self) -> None:
        """Async init upon WsRPC message event."""
        await self.initialize(True)
        await self._wsrpc.disconnect()

    def _on_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        """Received status notification from device."""
        if params is not None:
            if method == "NotifyFullStatus":
                self._status = params
            elif method == "NotifyStatus" and self._status is not None:
                self._status = dict(mergedicts(self._status, params))
            elif method == "NotifyEvent":
                self._event = params

        if not self._initializing and not self.initialized:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_init())
            return

        if self._update_listener and self.initialized:
            self._update_listener(self)

    @property
    def ip_address(self) -> str:
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self, async_init: bool = False) -> None:
        """Device initialization."""
        if self._initializing:
            raise RuntimeError("Already initializing")

        self._initializing = True
        self.initialized = False
        ip = self.options.ip_address
        try:
            self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

            if self.requires_auth:
                if self.options.username is None or self.options.password is None:
                    raise InvalidAuthError("auth missing and required")

                self._wsrpc.set_auth_data(
                    self.shelly["auth_domain"],
                    self.options.username,
                    self.options.password,
                )

            async with async_timeout.timeout(DEVICE_IO_TIMEOUT):
                await self._wsrpc.connect(self.aiohttp_session)
                await self.update_config()

                if not async_init or self._status is None:
                    await self.update_status()

            self.initialized = True
        except InvalidAuthError as err:
            self._last_error = InvalidAuthError(err)
            _LOGGER.debug("host %s: error: %r", ip, self._last_error)
            # Auth error during async init, used by sleeping devices
            # Will raise 'invalidAuthError' on next property read
            if not async_init:
                await self.shutdown()
                raise
            self.initialized = True
        except (*CONNECT_ERRORS, RpcCallError) as err:
            self._last_error = DeviceConnectionError(err)
            _LOGGER.debug("host %s: error: %r", ip, self._last_error)
            if not async_init:
                await self.shutdown()
                raise DeviceConnectionError(err) from err
        finally:
            self._initializing = False

        if self._update_listener and self.initialized:
            self._update_listener(self)

    async def shutdown(self) -> None:
        """Shutdown device."""
        self._update_listener = None

        if self._unsub_ws:
            self._unsub_ws()
            self._unsub_ws = None

        await self._wsrpc.disconnect()

    def subscribe_updates(self, update_listener: Callable) -> None:
        """Subscribe to device status updates."""
        self._update_listener = update_listener

    async def trigger_ota_update(self, beta: bool = False) -> None:
        """Trigger an ota update."""
        params = {"stage": "beta"} if beta else {"stage": "stable"}
        await self.call_rpc("Shelly.Update", params)

    async def trigger_reboot(self) -> None:
        """Trigger a device reboot."""
        await self.call_rpc("Shelly.Reboot")

    async def update_status(self) -> None:
        """Get device status from 'Shelly.GetStatus'."""
        self._status = await self.call_rpc("Shelly.GetStatus")

    async def update_config(self) -> None:
        """Get device config from 'Shelly.GetConfig'."""
        self._config = await self.call_rpc("Shelly.GetConfig")

    @property
    def requires_auth(self) -> bool:
        """Device check for authentication."""
        assert self.shelly

        if "auth_en" not in self.shelly:
            raise WrongShellyGen

        return bool(self.shelly["auth_en"])

    async def call_rpc(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call RPC method."""
        try:
            async with async_timeout.timeout(DEVICE_IO_TIMEOUT):
                return await self._wsrpc.call(method, params)
        except (InvalidAuthError, RpcCallError) as err:
            self._last_error = err
            raise
        except CONNECT_ERRORS as err:
            self._last_error = DeviceConnectionError(err)
            raise DeviceConnectionError from err

    @property
    def status(self) -> dict[str, Any]:
        """Get device status."""
        if not self.initialized:
            raise NotInitialized

        if self._status is None:
            raise InvalidAuthError

        return self._status

    @property
    def event(self) -> dict[str, Any] | None:
        """Get device event."""
        if not self.initialized:
            raise NotInitialized

        return self._event

    @property
    def config(self) -> dict[str, Any]:
        """Get device config."""
        if not self.initialized:
            raise NotInitialized

        if self._config is None:
            raise InvalidAuthError

        return self._config

    @property
    def gen(self) -> int:
        """Device generation: GEN2 - RPC."""
        return 2

    @property
    def firmware_version(self) -> str:
        """Device firmware version."""
        assert self.shelly

        if not self.initialized:
            raise NotInitialized

        return cast(str, self.shelly["fw_id"])

    @property
    def model(self) -> str:
        """Device model."""
        assert self.shelly

        if not self.initialized:
            raise NotInitialized

        return cast(str, self.shelly["model"])

    @property
    def hostname(self) -> str:
        """Device hostname."""
        assert self.shelly

        if not self.initialized:
            raise NotInitialized

        return cast(str, self.shelly["id"])

    @property
    def connected(self) -> bool:
        """Return true if device is connected."""
        return self._wsrpc.connected

    @property
    def last_error(self) -> ShellyError | None:
        """Return the last error during async device init."""
        return self._last_error
