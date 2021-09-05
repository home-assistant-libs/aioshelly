"""Shelly Gen2 RPC based device."""
import aiohttp

from .common import ConnectionOptions, get_info
from .const import MODEL_NAMES
from .exceptions import AuthRequired, NotInitialized
from .wsrpc import WsRPC


def mergedicts(dict1, dict2):
    """Deep dicts merge."""
    for k in set(dict1.keys()).union(dict2.keys()):
        if k in dict1 and k in dict2:
            if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                yield (k, dict(mergedicts(dict1[k], dict2[k])))
            else:
                yield (k, dict2[k])
        elif k in dict1:
            yield (k, dict1[k])
        else:
            yield (k, dict2[k])


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
        self._status = None
        self._device_info = None
        self._config = None
        self._wsrpc = WsRPC(options.ip_address, self._on_notification)
        self._update_listener = None
        self._initialized = False
        self._initializing = False

    @classmethod
    async def create(
        cls,
        aiohttp_session: aiohttp.ClientSession,
        options: ConnectionOptions,
        initialize: bool = True,
    ):
        """Device creation."""
        instance = cls(aiohttp_session, options)

        if initialize:
            await instance.initialize()

        return instance

    async def _on_notification(self, method, params):
        if method == "NotifyStatus":
            self._status = dict(mergedicts(self._status, params))

            if self._update_listener:
                self._update_listener(self)

    @property
    def ip_address(self):
        """Device ip address."""
        return self.options.ip_address

    async def initialize(self):
        """Device initialization."""
        self._initializing = True
        self._initialized = False
        try:
            await self._wsrpc.connect(self.aiohttp_session)
            self.shelly = await get_info(self.aiohttp_session, self.options.ip_address)

            if self.options.auth or not self.shelly["auth_en"]:
                await self.update_device_info()
                await self.update_config()
                await self.update_status()

            self._initialized = True
        finally:
            self._initializing = False

        if self._update_listener:
            self._update_listener(self)

    def shutdown(self):
        """Shutdown device."""
        self._update_listener = None
        self._wsrpc.disconnect()

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
    def initialized(self):
        """Device initialized."""
        return self._initialized

    @property
    def requires_auth(self):
        """Device check for authentication."""
        return self.shelly["auth_en"]

    @property
    def read_only(self):
        """Device check if can only read data."""
        return self.options.auth is None and self.requires_auth

    async def set_state(self, method, params):
        """Set state request (RPC Call)."""
        return await self._wsrpc.call(method, params)

    @property
    def status(self):
        """Get device status."""
        if not self._initialized:
            raise NotInitialized

        if self._status is None:
            raise AuthRequired

        return self._status

    @property
    def device_info(self):
        """Get device info."""
        if not self._initialized:
            raise NotInitialized

        if self._device_info is None:
            raise AuthRequired

        return self._device_info

    @property
    def config(self):
        """Get device config."""
        if not self._initialized:
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
        if not self._initialized:
            raise NotInitialized

        return self.shelly["fw_id"]

    @property
    def model(self):
        """Device model."""
        if not self._initialized:
            raise NotInitialized

        return self.shelly["model"]

    @property
    def model_name(self):
        """Device model name."""
        return MODEL_NAMES.get(self.model) or f"Unknown ({self.model})"

    @property
    def hostname(self):
        """Device hostname."""
        return self.device_info["id"]
