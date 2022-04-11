"""WsRpc for Shelly."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from asyncio import tasks
from dataclasses import dataclass
from typing import Any, Callable, cast

import aiohttp
import async_timeout
from aiohttp import ClientWebSocketResponse, WSMsgType, client_exceptions

from .const import NOTIFY_WS_CLOSED, WS_HEARTBEAT
from .exceptions import (
    CannotConnect,
    ConnectionClosed,
    ConnectionFailed,
    InvalidAuthError,
    InvalidMessage,
    JSONRPCError,
    RPCError,
    RPCTimeout,
)

_LOGGER = logging.getLogger(__name__)


def hex_hash(message: str) -> str:
    """Get hex representation of sha256 hash of string."""
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


HA2 = hex_hash("dummy_method:dummy_uri")


@dataclass
class AuthData:
    """RPC Auth data class."""

    realm: str
    username: str
    password: str

    def __post_init__(self) -> None:
        """Call after initialization."""
        self.ha1 = hex_hash(f"{self.username}:{self.realm}:{self.password}")

    def get_auth(self, nonce: int | None = None, n_c: int = 1) -> dict[str, Any]:
        """Get auth for RPC calls."""
        cnonce = int(time.time())
        if nonce is None:
            nonce = cnonce - 1800

        # https://shelly-api-docs.shelly.cloud/gen2/Overview/CommonDeviceTraits/#authentication-over-websocket
        hashed = hex_hash(f"{self.ha1}:{nonce}:{n_c}:{cnonce}:auth:{HA2}")

        return {
            "realm": self.realm,
            "username": self.username,
            "nonce": nonce,
            "cnonce": cnonce,
            "response": hashed,
            "algorithm": "SHA-256",
        }


@dataclass
class SessionData:
    """SessionData (src/dst/auth) class."""

    src: str | None
    dst: str | None
    auth: dict[str, Any] | None


class RPCCall:
    """RPCCall class."""

    def __init__(
        self,
        call_id: int,
        method: str,
        params: dict[str, Any] | None,
        session: SessionData,
    ):
        """Initialize RPC class."""
        self.auth = session.auth
        self.call_id = call_id
        self.params = params
        self.method = method
        self.src = session.src
        self.dst = session.dst
        self.resolve: asyncio.Future = asyncio.Future()

    @property
    def request_frame(self) -> dict[str, Any]:
        """Request frame."""
        msg = {
            "id": self.call_id,
            "method": self.method,
            "src": self.src,
        }
        for obj in ("params", "dst", "auth"):
            if getattr(self, obj) is not None:
                msg[obj] = getattr(self, obj)
        return msg


class WsRPC:
    """WsRPC class."""

    def __init__(self, ip_address: str, on_notification: Callable) -> None:
        """Initialize WsRPC class."""
        self._auth_data: AuthData | None = None
        self._ip_address = ip_address
        self._on_notification = on_notification
        self._rx_task: tasks.Task[None] | None = None
        self._client: ClientWebSocketResponse | None = None
        self._calls: dict[int, RPCCall] = {}
        self._call_id = 0
        self._session = SessionData(f"aios-{id(self)}", None, None)

    @property
    def _next_id(self) -> int:
        self._call_id += 1
        return self._call_id

    async def connect(self, aiohttp_session: aiohttp.ClientSession) -> None:
        """Connect to device."""
        if self.connected:
            raise RuntimeError("Already connected")

        _LOGGER.debug("Trying to connect to device at %s", self._ip_address)
        try:
            self._client = await aiohttp_session.ws_connect(
                f"http://{self._ip_address}/rpc", heartbeat=WS_HEARTBEAT
            )
        except (
            client_exceptions.WSServerHandshakeError,
            client_exceptions.ClientError,
        ) as err:
            raise CannotConnect(f"Error connecting to {self._ip_address}") from err

        self._rx_task = asyncio.create_task(self._rx_msgs())

        _LOGGER.info("Connected to %s", self._ip_address)

    async def disconnect(self) -> None:
        """Disconnect all sessions."""
        self._rx_task = None
        if self._client is None:
            return

        await self._client.close()

    def set_auth_data(self, realm: str, username: str, password: str) -> None:
        """Set authentication data and generate session auth."""
        self._auth_data = AuthData(realm, username, password)
        self._session.auth = self._auth_data.get_auth()

    async def _handle_call(self, frame_id: str) -> None:
        assert self._client

        await self._send_json(
            {
                "id": frame_id,
                "src": self._session.src,
                "error": {"code": 500, "message": "Not Implemented"},
            }
        )

    def _handle_frame(self, frame: dict[str, Any]) -> None:
        if peer_src := frame.get("src"):
            if self._session.dst is not None and peer_src != self._session.dst:
                _LOGGER.warning(
                    "Remote src changed: %s -> %s", self._session.dst, peer_src
                )
            self._session.dst = peer_src

        frame_id = frame.get("id")

        if method := frame.get("method"):
            # peer is invoking a method
            params = frame.get("params")
            if frame_id:
                # and expects a response
                _LOGGER.debug("handle call for frame_id: %s", frame_id)
                asyncio.create_task(self._handle_call(frame_id))
            else:
                # this is a notification
                _LOGGER.debug("Notification: %s %s", method, params)
                self._on_notification(method, params)

        elif frame_id:
            # looks like a response
            if frame_id not in self._calls:
                _LOGGER.warning("Response for an unknown request id: %s", frame_id)
                return

            call = self._calls.pop(frame_id)
            if not call.resolve.cancelled():
                call.resolve.set_result(frame)

        else:
            _LOGGER.warning("Invalid frame: %s", frame)

    async def _rx_msgs(self) -> None:
        assert self._client

        while not self._client.closed:
            try:
                frame = await self._receive_json_or_raise()
            except ConnectionClosed:
                break

            if not self._client.closed:
                self._handle_frame(frame)

        _LOGGER.debug("Websocket connection closed")

        for call_item in self._calls.values():
            call_item.resolve.cancel()
        self._calls.clear()

        if not self._client.closed:
            await self._client.close()

        self._client = None
        self._on_notification(NOTIFY_WS_CLOSED)

    async def _receive_json_or_raise(self) -> dict[str, Any]:
        """Receive json or raise."""
        assert self._client
        msg = await self._client.receive()

        if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
            raise ConnectionClosed("Connection was closed.")

        if msg.type == WSMsgType.ERROR:
            raise ConnectionFailed()

        if msg.type != WSMsgType.TEXT:
            raise InvalidMessage(f"Received non-Text message: {msg.type}")

        _LOGGER.debug("recv(%s): %s", self._ip_address, msg.data)
        try:
            data: dict[str, Any] = msg.json()
        except ValueError as err:
            raise InvalidMessage("Received invalid JSON.") from err

        return data

    @property
    def connected(self) -> bool:
        """Return if we're currently connected."""
        return self._client is not None and not self._client.closed

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: int = 10,
        handle_auth: bool = True,
    ) -> dict[str, Any]:
        """Websocket RPC call."""
        # Try request with initial/last call auth data
        resp = await self._rpc_call(method, params, timeout)
        if "result" in resp:
            return cast(dict, resp["result"])

        try:
            code, msg = resp["error"]["code"], resp["error"]["message"]
        except KeyError as err:
            raise RPCError(f"bad response: {resp}") from err

        if code != 401:
            raise JSONRPCError(code, msg)
        if not handle_auth or self._auth_data is None:
            raise InvalidAuthError(code, msg)

        # Update auth from response and try with new auth data
        auth = json.loads(msg)
        self._session.auth = self._auth_data.get_auth(auth["nonce"], auth.get("nc", 1))
        return await self.call(method, params, timeout, handle_auth=False)

    async def _rpc_call(
        self, method: str, params: dict[str, Any] | None, timeout: int
    ) -> dict[str, Any]:
        """Websocket RPC call."""
        if self._client is None:
            raise RuntimeError("Not connected")

        call = RPCCall(self._next_id, method, params, self._session)
        self._calls[call.call_id] = call
        await self._send_json(call.request_frame)

        try:
            async with async_timeout.timeout(timeout):
                resp: dict[str, Any] = await call.resolve
        except asyncio.TimeoutError as exc:
            _LOGGER.warning("%s timed out: %s", call, exc)
            raise RPCTimeout(call) from exc
        except Exception as exc:
            _LOGGER.error("%s ???: %s", call, exc)
            raise RPCError(call, exc) from exc

        _LOGGER.debug("%s(%s) -> %s", call.method, call.params, resp)
        return resp

    async def _send_json(self, data: dict[str, Any]) -> None:
        """Send json frame to device."""
        _LOGGER.debug("send(%s): %s", self._ip_address, data)
        assert self._client
        await self._client.send_json(data)
