"""Shelly Gen2 RPC based device."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from enum import Enum, auto
from typing import Any, cast

from aiohttp import ClientSession

from ..common import ConnectionOptions, IpOrOptionsType, get_info, process_ip_or_options
from ..const import (
    CONNECT_ERRORS,
    DEVICE_IO_TIMEOUT,
    FIRMWARE_PATTERN,
    GEN2,
    GEN2_MIN_FIRMWARE_DATE,
    GEN3_MIN_FIRMWARE_DATE,
    NOTIFY_WS_CLOSED,
)
from ..exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
    NotInitialized,
    RpcCallError,
    ShellyError,
    WrongShellyGen,
)
from .models import (
    ShellyBLEConfig,
    ShellyBLESetConfig,
    ShellyScript,
    ShellyScriptCode,
    ShellyWsConfig,
    ShellyWsSetConfig,
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


class RpcUpdateType(Enum):
    """RPC Update type."""

    EVENT = auto()
    STATUS = auto()
    INITIALIZED = auto()
    DISCONNECTED = auto()
    UNKNOWN = auto()
    ONLINE = auto()


class RpcDevice:
    """Shelly RPC device representation."""

    def __init__(
        self,
        ws_context: WsServer,
        aiohttp_session: ClientSession,
        options: ConnectionOptions,
    ) -> None:
        """Device init."""
        self.aiohttp_session: ClientSession = aiohttp_session
        self.options: ConnectionOptions = options
        self._shelly: dict[str, Any] | None = None
        self._status: dict[str, Any] | None = None
        self._event: dict[str, Any] | None = None
        self._config: dict[str, Any] | None = None
        self._wsrpc = WsRPC(
            options.ip_address, self._on_notification, port=options.port
        )
        sub_id = options.ip_address
        if options.device_mac:
            sub_id = options.device_mac
        self._unsub_ws: Callable | None = ws_context.subscribe_updates(
            sub_id, self._wsrpc.handle_frame
        )
        self._update_listener: Callable | None = None
        self.initialized: bool = False
        self._initializing: bool = False
        self._last_error: ShellyError | None = None

    @classmethod
    async def create(
        cls: type[RpcDevice],
        aiohttp_session: ClientSession,
        ws_context: WsServer,
        ip_or_options: IpOrOptionsType,
    ) -> RpcDevice:
        """Device creation."""
        options = await process_ip_or_options(ip_or_options)
        _LOGGER.debug(
            "host %s:%s: RPC device create, MAC: %s",
            options.ip_address,
            options.port,
            options.device_mac,
        )
        return cls(ws_context, aiohttp_session, options)

    def _on_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        """Received status notification from device."""
        update_type = RpcUpdateType.UNKNOWN
        if params is not None:
            if method == "NotifyFullStatus":
                self._status = params
                update_type = RpcUpdateType.STATUS
            elif method == "NotifyStatus" and self._status is not None:
                self._status = dict(mergedicts(self._status, params))
                update_type = RpcUpdateType.STATUS
            elif method == "NotifyEvent":
                self._event = params
                update_type = RpcUpdateType.EVENT
        elif method == NOTIFY_WS_CLOSED:
            update_type = RpcUpdateType.DISCONNECTED

        if not self._update_listener or self._initializing:
            return

        if not self.initialized:
            self._update_listener(self, RpcUpdateType.ONLINE)
            return

        self._update_listener(self, update_type)

    @property
    def ip_address(self) -> str:
        """Device ip address."""
        return self.options.ip_address

    @property
    def port(self) -> int:
        """Device port."""
        return self.options.port

    async def initialize(self) -> None:
        """Device initialization."""
        _LOGGER.debug("host %s:%s: RPC device initialize", self.ip_address, self.port)
        if self._initializing:
            raise RuntimeError("Already initializing")

        self._initializing = True

        # First initialize may already have status from wakeup event
        # If device is initialized again we need to fetch new status
        if self.initialized:
            self.initialized = False
            self._status = None

        ip = self.options.ip_address
        port = self.options.port
        try:
            self._shelly = await get_info(
                self.aiohttp_session,
                self.options.ip_address,
                self.options.device_mac,
                self.options.port,
            )

            if self.requires_auth:
                if self.options.username is None or self.options.password is None:
                    raise InvalidAuthError("auth missing and required")  # noqa: TRY301

                self._wsrpc.set_auth_data(
                    self.shelly["auth_domain"],
                    self.options.username,
                    self.options.password,
                )

            async with asyncio.timeout(DEVICE_IO_TIMEOUT):
                await self._wsrpc.connect(self.aiohttp_session)
                await self.update_config()

                if self._status is None:
                    await self.update_status()

            self.initialized = True
        except InvalidAuthError as err:
            self._last_error = InvalidAuthError(err)
            _LOGGER.debug("host %s:%s: error: %r", ip, port, self._last_error)
            await self._disconnect_websocket()
            raise
        except MacAddressMismatchError as err:
            self._last_error = err
            _LOGGER.debug("host %s:%s: error: %r", ip, port, err)
            await self._disconnect_websocket()
            raise
        except (*CONNECT_ERRORS, RpcCallError) as err:
            self._last_error = DeviceConnectionError(err)
            _LOGGER.debug("host %s:%s: error: %r", ip, port, self._last_error)
            await self._disconnect_websocket()
            raise DeviceConnectionError(err) from err
        finally:
            self._initializing = False

        if self._update_listener and self.initialized:
            self._update_listener(self, RpcUpdateType.INITIALIZED)

    async def shutdown(self) -> None:
        """Shutdown device and remove the listener.

        This method will unsubscribe the update listener and disconnect the websocket.

        """
        _LOGGER.debug("host %s:%s: RPC device shutdown", self.ip_address, self.port)
        self._update_listener = None
        await self._disconnect_websocket()

    async def _disconnect_websocket(self) -> None:
        """Disconnect websocket."""
        if self._unsub_ws:
            try:
                self._unsub_ws()
            except KeyError as err:
                _LOGGER.error(
                    "host %s:%s error during shutdown: %r",
                    self.ip_address,
                    self.port,
                    err,
                )
            self._unsub_ws = None

        await self._wsrpc.disconnect()

    def subscribe_updates(self, update_listener: Callable) -> None:
        """Subscribe to device status updates."""
        self._update_listener = update_listener

    async def trigger_ota_update(self, beta: bool = False) -> None:
        """Trigger an ota update."""
        params = {"stage": "beta"} if beta else {"stage": "stable"}
        await self.call_rpc("Shelly.Update", params)

    async def trigger_reboot(self, delay_ms: int = 1000) -> None:
        """Trigger a device reboot."""
        await self.call_rpc("Shelly.Reboot", {"delay_ms": delay_ms})

    async def update_status(self) -> None:
        """Get device status from 'Shelly.GetStatus'."""
        self._status = await self.call_rpc("Shelly.GetStatus")

    async def update_config(self) -> None:
        """Get device config from 'Shelly.GetConfig'."""
        self._config = await self.call_rpc("Shelly.GetConfig")

    async def script_list(self) -> list[ShellyScript]:
        """Get a list of scripts from 'Script.List'."""
        data = await self.call_rpc("Script.List")
        scripts: list[ShellyScript] = data["scripts"]
        return scripts

    async def script_getcode(self, script_id: int) -> ShellyScriptCode:
        """Get script code from 'Script.GetCode'."""
        return cast(
            ShellyScriptCode, await self.call_rpc("Script.GetCode", {"id": script_id})
        )

    async def script_putcode(self, script_id: int, code: str) -> None:
        """Set script code from 'Script.PutCode'."""
        await self.call_rpc("Script.PutCode", {"id": script_id, "code": code})

    async def script_create(self, name: str) -> None:
        """Create a script using 'Script.Create'."""
        await self.call_rpc("Script.Create", {"name": name})

    async def script_start(self, script_id: int) -> None:
        """Start a script using 'Script.Start'."""
        await self.call_rpc("Script.Start", {"id": script_id})

    async def script_stop(self, script_id: int) -> None:
        """Stop a script using 'Script.Stop'."""
        await self.call_rpc("Script.Stop", {"id": script_id})

    async def ble_setconfig(self, enable: bool, enable_rpc: bool) -> ShellyBLESetConfig:
        """Enable or disable ble with BLE.SetConfig."""
        return cast(
            ShellyBLESetConfig,
            await self.call_rpc(
                "BLE.SetConfig",
                {"config": {"enable": enable, "rpc": {"enable": enable_rpc}}},
            ),
        )

    async def ble_getconfig(self) -> ShellyBLEConfig:
        """Get the BLE config with BLE.GetConfig."""
        return cast(ShellyBLEConfig, await self.call_rpc("BLE.GetConfig"))

    async def ws_setconfig(
        self, enable: bool, server: str, ssl_ca: str = "*"
    ) -> ShellyWsSetConfig:
        """Set the outbound websocket config."""
        return cast(
            ShellyWsSetConfig,
            await self.call_rpc(
                "Ws.SetConfig",
                {"config": {"enable": enable, "server": server, "ssl_ca": ssl_ca}},
            ),
        )

    async def ws_getconfig(self) -> ShellyWsConfig:
        """Get the outbound websocket config."""
        return cast(ShellyWsConfig, await self.call_rpc("Ws.GetConfig"))

    async def update_outbound_websocket(self, server: str) -> bool:
        """Update the outbound websocket (if needed).

        Returns True if the device was restarted.

        Raises RpcCallError if set failed.
        """
        ws_config = await self.ws_getconfig()
        if ws_config["enable"] and ws_config["server"] == server:
            return False
        ws_enable = await self.ws_setconfig(enable=True, server=server)
        if not ws_enable["restart_required"]:
            return False
        _LOGGER.info(
            "Outbound websocket enabled, restarting device %s", self.ip_address
        )
        await self.trigger_reboot(3500)
        return True

    @property
    def requires_auth(self) -> bool:
        """Device check for authentication."""
        if "auth_en" not in self.shelly:
            raise WrongShellyGen

        return bool(self.shelly["auth_en"])

    async def call_rpc(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call RPC method."""
        try:
            async with asyncio.timeout(DEVICE_IO_TIMEOUT):
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
    def shelly(self) -> dict[str, Any]:
        """Device firmware version."""
        if self._shelly is None:
            raise NotInitialized

        return self._shelly

    @property
    def gen(self) -> int:
        """Device generation: GEN2/3 - RPC."""
        if self._shelly is None:
            raise NotInitialized

        return cast(int, self._shelly["gen"])

    @property
    def firmware_version(self) -> str:
        """Device firmware version."""
        return cast(str, self.shelly["fw_id"])

    @property
    def version(self) -> str:
        """Device version."""
        return cast(str, self.shelly["ver"])

    @property
    def model(self) -> str:
        """Device model."""
        return cast(str, self.shelly["model"])

    @property
    def hostname(self) -> str:
        """Device hostname."""
        return cast(str, self.shelly["id"])

    @property
    def name(self) -> str:
        """Device name."""
        return cast(str, self.config["sys"]["device"].get("name") or self.hostname)

    @property
    def connected(self) -> bool:
        """Return true if device is connected."""
        return self._wsrpc.connected

    @property
    def last_error(self) -> ShellyError | None:
        """Return the last error during async device init."""
        return self._last_error

    @property
    def firmware_supported(self) -> bool:
        """Return True if device firmware version is supported."""
        fw_ver = GEN2_MIN_FIRMWARE_DATE if self.gen == GEN2 else GEN3_MIN_FIRMWARE_DATE

        match = FIRMWARE_PATTERN.search(self.firmware_version)

        if match is None:
            return False

        # We compare firmware release dates because Shelly version numbering is
        # inconsistent, sometimes the word is used as the version number.
        return int(match[0]) >= fw_ver
