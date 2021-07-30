"""WsRpc for Shelly."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

import aiohttp
from aiohttp import ClientWebSocketResponse, client_exceptions

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

    id: int
    method: str
    params: Any  # None or JSON-serializable
    src: str | None = None
    dst: str | None = None
    sent_at: datetime | None = None
    resolve: asyncio.Future | None = None

    @property
    def request_frame(self):
        """Request frame."""
        msg = {
            "id": self.id,
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
        self.ip_address = ip_address
        self.on_notification = on_notification
        self.rx_task = None
        self.websocket: ClientWebSocketResponse | None = None
        self.calls: Dict[str, str] = {}
        self._call_id = 1
        self.src = f"aios-{id(self)}"
        self.dst = None

    @property
    def _next_id(self):
        self._call_id += 1
        return self._call_id

    async def connect(self, aiohttp_session):
        """Connect to device."""
        if self.websocket:
            _LOGGER.debug("%s already connected", self.ip_address)
            return

        _LOGGER.debug("Trying to connect to device at %s", self.ip_address)
        try:
            self.websocket = await aiohttp_session.ws_connect(
                f"http://{self.ip_address}/rpc"
            )
        except (
            client_exceptions.WSServerHandshakeError,
            client_exceptions.ClientError,
        ) as err:
            raise CannotConnect(f"Error connecting to {self.ip_address}") from err

        asyncio.create_task(self._rx_msgs())

        _LOGGER.info("Connected to %s", self.ip_address)

    async def disconnect(self):
        """Disconnect all sessions."""
        if self.websocket is None:
            return

        websocket, self.websocket = self.websocket, None
        await websocket.close()

        for call_item in self.calls.items():
            call_item.future.cancel()

        self.calls = {}

    async def _handle_call(self, frame_id):
        await self.websocket.send_json(
            {
                "id": frame_id,
                "src": self.src,
                "error": {"code": 500, "message": "Not Implemented"},
            }
        )

    async def _handle_frame(self, frame):
        if peer_src := frame.get("src", None):
            if self.dst is not None and peer_src != self.dst:
                _LOGGER.warning("Remote src changed: %s -> %s", self.dst, peer_src)
            self.dst = peer_src

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
                await self.on_notification(method, params)

        elif frame_id:
            # looks like a response
            if frame_id not in self.calls:
                _LOGGER.warning("Response for an unknown request id: %s", frame_id)
                return

            call = self.calls.pop(frame_id)
            call.resolve.set_result(frame)

        else:
            _LOGGER.warning("Invalid frame: %s", frame)

    async def _rx_msgs(self):
        async for msg in self.websocket:
            _LOGGER.debug("Receive %s: %s", msg.type, msg.data)
            if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                _LOGGER.warning("%s disconnected", self)
                self.websocket = None
                return

            try:
                frame = msg.json()
            except ValueError as err:
                raise InvalidMessage("Received invalid JSON.") from err
            else:
                await self._handle_frame(frame)

    @property
    def connected(self) -> bool:
        """Return if we're currently connected."""
        return self.websocket is not None and not self.websocket.closed

    async def call(self, method, params=None, timeout=10):
        """Websocket RPC call."""
        call = RPCCall(self._next_id, method, params)
        call.resolve = asyncio.Future()
        call.src = self.src
        call.dst = self.dst

        self.calls[call.id] = call
        await self.websocket.send_json(call.request_frame)
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
