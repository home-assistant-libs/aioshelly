"""WsRpc for Shelly."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from aiohttp import ClientWebSocketResponse, client_exceptions

from .const import WS_HEARTBEAT_SEC
from .exceptions import (
    CannotConnect,
    InvalidMessage,
    JSONRPCError,
    RPCError,
    RPCTimeout,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RPCCall:
    """RPCCall class."""

    call_id: int
    method: str
    params: Dict[str, Any] | None
    src: str | None = None
    dst: str | None = None
    sent_at: datetime | None = None
    resolve: asyncio.Future | None = None

    @property
    def request_frame(self):
        """Request frame."""
        msg = {
            "id": self.call_id,
            "method": self.method,
            "src": self.src,
        }
        for obj in ("params", "dst"):
            if getattr(self, obj) is not None:
                msg[obj] = getattr(self, obj)
        return msg


class WsRPC:
    """WsRPC class."""

    def __init__(self, ip_address: str, on_notification):
        """Initialize WsRPC class."""
        self._ip_address = ip_address
        self._on_notification = on_notification
        self._rx_task = None
        self._websocket: ClientWebSocketResponse | None = None
        self._calls: Dict[str, str] = {}
        self._call_id = 1
        self._src = f"aios-{id(self)}"
        self._dst = None

    @property
    def _next_id(self):
        self._call_id += 1
        return self._call_id

    async def connect(self, aiohttp_session):
        """Connect to device."""
        if self.connected:
            _LOGGER.debug("%s already connected", self._ip_address)
            return

        _LOGGER.debug("Trying to connect to device at %s", self._ip_address)
        try:
            self._websocket = await aiohttp_session.ws_connect(
                f"http://{self._ip_address}/rpc", heartbeat=WS_HEARTBEAT_SEC
            )
        except (
            client_exceptions.WSServerHandshakeError,
            client_exceptions.ClientError,
        ) as err:
            raise CannotConnect(f"Error connecting to {self._ip_address}") from err

        self._rx_task = asyncio.create_task(self._rx_msgs())

        _LOGGER.info("Connected to %s", self._ip_address)

    async def disconnect(self):
        """Disconnect all sessions."""
        if self._websocket is None:
            return

        websocket, self._websocket = self._websocket, None
        await websocket.close()

        for call_item in self._calls.items():
            call_item.future.cancel()

        self._calls = {}
        self._rx_task = None

    async def _handle_call(self, frame_id):
        await self._websocket.send_json(
            {
                "id": frame_id,
                "src": self._src,
                "error": {"code": 500, "message": "Not Implemented"},
            }
        )

    async def _handle_frame(self, frame):
        if peer_src := frame.get("src", None):
            if self._dst is not None and peer_src != self._dst:
                _LOGGER.warning("Remote src changed: %s -> %s", self._dst, peer_src)
            self._dst = peer_src

        frame_id = frame.get("id", None)
        method = frame.get("method", None)

        if method:
            # peer is invoking a method
            params = frame.get("params", None)
            if frame_id:
                # and expects a response
                _LOGGER.debug("handle call for frame_id: %s", frame_id)
                await self._handle_call(frame_id)
            else:
                # this is a notification
                _LOGGER.debug("Notification: %s %s", method, params)
                await self._on_notification(method, params)

        elif frame_id:
            # looks like a response
            if frame_id not in self._calls:
                _LOGGER.warning("Response for an unknown request id: %s", frame_id)
                return

            call = self._calls.pop(frame_id)
            call.resolve.set_result(frame)

        else:
            _LOGGER.warning("Invalid frame: %s", frame)

    async def _rx_msgs(self):
        async for msg in self._websocket:
            _LOGGER.debug("Received Message: Type: %s,  Data: %s", msg.type, msg.data)

            try:
                frame = msg.json()
            except ValueError as err:
                raise InvalidMessage("Received invalid JSON.") from err
            else:
                await self._handle_frame(frame)

        error = str(self._websocket.exception()) if self._websocket else "Disconnected"
        _LOGGER.debug("Websocket error: %s", error)
        await self._on_notification("WebSocketClosed", {"error": error})

    @property
    def connected(self) -> bool:
        """Return if we're currently connected."""
        return self._websocket is not None and not self._websocket.closed

    async def call(self, method, params=None, timeout=10):
        """Websocket RPC call."""
        call = RPCCall(self._next_id, method, params)
        call.resolve = asyncio.Future()
        call.src = self._src
        call.dst = self._dst

        self._calls[call.call_id] = call
        await self._websocket.send_json(call.request_frame)
        call.sent_at = datetime.utcnow()

        try:
            resp = await asyncio.wait_for(call.resolve, timeout)
        except asyncio.TimeoutError as exc:
            _LOGGER.warning("%s timed out: %s", call, exc)
            raise RPCTimeout(call) from exc
        except Exception as exc:
            _LOGGER.error("%s ???: %s", call, exc)
            raise RPCError(call, exc) from exc

        if "result" in resp:
            _LOGGER.debug("%s(%s) -> %s", call.method, call.params, resp["result"])
            return resp["result"]

        try:
            code, msg = resp["error"]["code"], resp["error"]["message"]
            raise JSONRPCError(code, msg)
        except KeyError as err:
            raise RPCError(f"bad response: {resp}") from err
