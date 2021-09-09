"""Shelly Gen2 RPC based device."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

import aiohttp

from .common import ConnectionOptions, IpOrOptionsType, get_info, process_ip_or_options
from .exceptions import AuthRequired, NotInitialized, WrongShellyGen
from .wsrpc import WsRPC


def mergedicts(dict1, dict2):
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
        self.aiohttp_session = aiohttp_session
        self.options = options
        self.shelly = None
        self._status: Dict[str, Any] | None = None
        self._event: Dict[str, Any] | None = None
        self._device_info = None
        self._config = None
        self._wsrpc = WsRPC(options.ip_address, self._on_notification)
        self._update_listener = None
        self.initialized = False
        self._initializing = False

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        ip_or_options: IpOrOptionsType,
        initialize: bool = True,
    ):
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        instance = cls(aiohttp_session, options)

        if initialize:
            await instance.initialize()

        return instance

    def _on_notification(self, method, params=None):
        if params is not None:
            if method == "NotifyStatus":
                self._status = dict(mergedicts(self._status, params))
            elif method == "NotifyEvent":
                self._event = params

        if self._update_listener:
            self._update_listener(self)

    @property
    def ip_address(self):
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self):
        """Device initialization."""
        if self._initializing:
            raise RuntimeError("Already initializing")

        self._initializing = True
        self.initialized = False
        try:
            self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

            if self.options.auth or not self.requires_auth:
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

    async def shutdown(self):
        """Shutdown device."""
        self._update_listener = None
        await self._wsrpc.disconnect()

    def subscribe_updates(self, update_listener):
        """Subscribe to device status updates."""
        self._update_listener = update_listener

    async def update_status(self):
        """Get device status from 'Shelly.GetStatus'."""
        self._status = await self._wsrpc.call("Shelly.GetStatus")

    async def update_device_info(self):
        """Get device info from 'Shelly.GetDeviceInfo'."""
        self._device_info = await self._wsrpc.call("Shelly.GetDeviceInfo")

    async def update_config(self):
        """Get device config from 'Shelly.GetConfig'."""
        self._config = await self._wsrpc.call("Shelly.GetConfig")

    @property
    def requires_auth(self):
        """Device check for authentication."""
        if "auth_en" not in self.shelly:
            raise WrongShellyGen

        return self.shelly["auth_en"]

    async def call_rpc(self, method, params):
        """Call RPC method."""
        return await self._wsrpc.call(method, params)

    @property
    def status(self):
        """Get device status."""
        if not self.initialized:
            raise NotInitialized

        if self._status is None:
            raise AuthRequired

        return self._status

    @property
    def event(self):
        """Get device event."""
        if not self.initialized:
            raise NotInitialized

        return self._event

    @property
    def device_info(self):
        """Get device info."""
        if not self.initialized:
            raise NotInitialized

        if self._device_info is None:
            raise AuthRequired

        return self._device_info

    @property
    def config(self):
        """Get device config."""
        if not self.initialized:
            raise NotInitialized

        if self._config is None:
            raise AuthRequired

        return self._config

    @property
    def gen(self):
        """Device generation: GEN2 - RPC."""
        return 2

    @property
    def firmware_version(self):
        """Device firmware version."""
        if not self.initialized:
            raise NotInitialized

        return self.shelly["fw_id"]

    @property
    def model(self):
        """Device model."""
        if not self.initialized:
            raise NotInitialized

        return self.shelly["model"]

    @property
    def hostname(self):
        """Device hostname."""
        return self.device_info["id"]

    @property
    def connected(self):
        """Return true if device is connected."""
        return self._wsrpc.connected
