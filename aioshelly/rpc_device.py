"""Shelly Gen2 RPC based device."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, cast

import aiohttp
from aiohttp.client import ClientSession

from .common import ConnectionOptions, IpOrOptionsType, get_info, process_ip_or_options
from .exceptions import AuthRequired, NotInitialized, WrongShellyGen
from .wsrpc import WsRPC


def mergedicts(dict1: dict, dict2: dict) -> dict:
    """Deep dicts merge."""
    result = dict(dict1)
    result.update(dict2)
    for key, value in result.items():
        if isinstance(value, dict) and isinstance(dict1.get(key), dict):
            result[key] = mergedicts(dict1[key], value)
    return result


class RpcDevice:
    """Shelly RPC device reppresentation."""

    def __init__(
        self,
        aiohttp_session: aiohttp.ClientSession,
        options: ConnectionOptions,
    ):
        """Device init."""
        self.aiohttp_session: ClientSession = aiohttp_session
        self.options: ConnectionOptions = options
        self.shelly: dict[str, Any] | None = None
        self._status: dict[str, Any] | None = None
        self._event: dict[str, Any] | None = None
        self._device_info: dict[str, Any] | None = None
        self._config: dict[str, Any] | None = None
        self._wsrpc = WsRPC(options.ip_address, self._on_notification)
        self._update_listener: Callable | None = None
        self.initialized: bool = False
        self._initializing: bool = False

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        ip_or_options: IpOrOptionsType,
        initialize: bool = True,
    ) -> RpcDevice:
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        instance = cls(aiohttp_session, options)

        if initialize:
            await instance.initialize()

        return instance

    def _on_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        if params is not None:
            if method == "NotifyStatus":
                if self._status is None:
                    return
                self._status = dict(mergedicts(self._status, params))
            elif method == "NotifyEvent":
                self._event = params

        if self._update_listener:
            self._update_listener(self)

    @property
    def ip_address(self) -> str:
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self) -> None:
        """Device initialization."""
        if self._initializing:
            raise RuntimeError("Already initializing")

        self._initializing = True
        self.initialized = False
        try:
            self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

            if self.requires_auth:
                if self.options.username is None or self.options.password is None:
                    raise AuthRequired

                self._wsrpc.set_auth_data(
                    self.shelly["auth_domain"],
                    self.options.username,
                    self.options.password,
                )

            await self._wsrpc.connect(self.aiohttp_session)
            await asyncio.gather(
                self.update_device_info(),
                self.update_config(),
                self.update_status(),
            )
            self.initialized = True
        finally:
            self._initializing = False

        if self._update_listener:
            self._update_listener(self)

    async def shutdown(self) -> None:
        """Shutdown device."""
        self._update_listener = None
        await self._wsrpc.disconnect()

    def subscribe_updates(self, update_listener: Callable) -> None:
        """Subscribe to device status updates."""
        self._update_listener = update_listener

    async def trigger_ota_update(self, beta: bool = False) -> None:
        """Trigger an ota update."""
        params = {"stage": "beta"} if beta else {"stage": "stable"}
        await self._wsrpc.call("Shelly.Update", params)

    async def trigger_reboot(self) -> None:
        """Trigger a device reboot."""
        await self._wsrpc.call("Shelly.Reboot")

    async def update_status(self) -> None:
        """Get device status from 'Shelly.GetStatus'."""
        self._status = await self._wsrpc.call("Shelly.GetStatus")

    async def update_device_info(self) -> None:
        """Get device info from 'Shelly.GetDeviceInfo'."""
        self._device_info = await self._wsrpc.call("Shelly.GetDeviceInfo")

    async def update_config(self) -> None:
        """Get device config from 'Shelly.GetConfig'."""
        self._config = await self._wsrpc.call("Shelly.GetConfig")

    @property
    def requires_auth(self) -> bool:
        """Device check for authentication."""
        assert self.shelly

        if "auth_en" not in self.shelly:
            raise WrongShellyGen

        return bool(self.shelly["auth_en"])

    async def call_rpc(
        self, method: str, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Call RPC method."""
        return await self._wsrpc.call(method, params)

    @property
    def status(self) -> dict[str, Any]:
        """Get device status."""
        if not self.initialized:
            raise NotInitialized

        if self._status is None:
            raise AuthRequired

        return self._status

    @property
    def event(self) -> dict[str, Any] | None:
        """Get device event."""
        if not self.initialized:
            raise NotInitialized

        return self._event

    @property
    def device_info(self) -> dict[str, Any]:
        """Get device info."""
        if not self.initialized:
            raise NotInitialized

        if self._device_info is None:
            raise AuthRequired

        return self._device_info

    @property
    def config(self) -> dict[str, Any]:
        """Get device config."""
        if not self.initialized:
            raise NotInitialized

        if self._config is None:
            raise AuthRequired

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
        return cast(str, self.device_info["id"])

    @property
    def connected(self) -> bool:
        """Return true if device is connected."""
        return self._wsrpc.connected
