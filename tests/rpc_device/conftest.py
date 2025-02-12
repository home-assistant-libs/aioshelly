"""Tests for RPC device."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from aiohttp.client import ClientSession
from aiohttp.client_ws import ClientWebSocketResponse
from aiohttp.http_websocket import WSMessage, WSMsgType
from orjson import dumps

from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device.device import RpcDevice, WsServer
from aioshelly.rpc_device.wsrpc import DEFAULT_HTTP_PORT, AuthData, RPCSource, WsRPC


class ResponseMocker:
    """Mocker for a WebSocket responses."""

    def __init__(self) -> None:
        """Initialize the mocker."""
        self.queue: asyncio.Queue[WSMessage] = asyncio.Queue()

    async def mock_ws_message(self, response: WSMessage) -> None:
        """Mock a WebSocket message."""
        await self.queue.put(response)

    async def read(self) -> str:
        """Read a message."""
        return await self.queue.get()


class NotifyHistory:
    """History of notifications."""

    def __init__(self) -> None:
        """Initialize the history."""
        self.history = []

    def save(self, rpc_source: RPCSource, method: str, data: dict | None) -> None:
        """Save a notification."""
        self.history.append((rpc_source, method, data))


class WsRPCMocker(WsRPC):
    """RPC WebSocket mocker."""

    def __init__(
        self,
        response_mocker: ResponseMocker,
        ip_address: str,
        on_notification: Callable[[RPCSource, str, dict | None], None],
        port: int = DEFAULT_HTTP_PORT,
    ) -> None:
        """Initialize the RPC WebSocket mocker."""
        super().__init__(ip_address, on_notification, port)
        self.response_mocker = response_mocker
        self.responses: list[dict[str, Any]] = []
        self.next_id_mock = 0

    async def calls_with_mocked_responses(
        self,
        calls: list[tuple[str, dict[str, Any] | None]],
        responses: list[dict[str, Any]],
    ) -> list[str]:
        """Call methods with mocked responses."""
        self.next_id_mock = self._call_id
        self.responses = responses
        return await self.calls(calls, 0.1)

    async def _send_json(self, data: dict[str, Any]) -> None:
        """Instrumented send JSON data to mock a response."""
        await super()._send_json(data)
        await self._send_next_response()

    async def _send_next_response(self) -> None:
        """Send the next response."""
        response = self.responses.pop(0)
        shallow_copy = response.copy()
        self.next_id_mock += 1
        shallow_copy["id"] = self.next_id_mock
        response_with_correct_id = dumps(shallow_copy).decode()
        await self.response_mocker.mock_ws_message(
            WSMessage(WSMsgType.TEXT, response_with_correct_id, None)
        )


@pytest_asyncio.fixture
async def rpc_websocket_responses() -> AsyncGenerator[ResponseMocker, None]:
    """Fixture for a WebSocket responses."""
    return ResponseMocker()


@pytest_asyncio.fixture
async def rpc_websocket_response(
    rpc_websocket_responses: ResponseMocker,
) -> AsyncGenerator[ClientWebSocketResponse, None]:
    """Fixture for a WebSocket response."""
    mock = MagicMock(spec=ClientWebSocketResponse)
    mock.receive = rpc_websocket_responses.read
    mock.closed = False
    return mock


@pytest_asyncio.fixture
async def client_session(
    rpc_websocket_response: ClientWebSocketResponse,
) -> AsyncGenerator[ClientSession, None]:
    """Fixture for a ClientSession."""
    mock = MagicMock(spec=ClientSession)
    mock.ws_connect = AsyncMock(return_value=rpc_websocket_response)
    return mock


@pytest_asyncio.fixture
async def notify_history() -> AsyncGenerator[NotifyHistory, None]:
    """Fixture to track notify history."""
    return NotifyHistory()


@pytest_asyncio.fixture
async def ws_rpc(
    rpc_websocket_response: ClientWebSocketResponse,
    client_session: ClientSession,
    notify_history: NotifyHistory,
    rpc_websocket_responses: ResponseMocker,
) -> AsyncGenerator[WsRPCMocker, None]:
    """Fixture for an RPC WebSocket."""
    with patch("aioshelly.rpc_device.wsrpc.ClientWebSocketResponse") as mock:
        mock.return_value = rpc_websocket_response
        ws_rpc = WsRPCMocker(rpc_websocket_responses, "127.0.0.1", notify_history.save)
        await ws_rpc.connect(client_session)
        yield ws_rpc
        await ws_rpc.disconnect()


@pytest_asyncio.fixture
async def ws_rpc_with_auth(ws_rpc: WsRPCMocker) -> AsyncGenerator[WsRPCMocker, None]:
    """Fixture for an RPC WebSocket with authentication."""
    ws_rpc._auth_data = AuthData("any", "any", "any")
    yield ws_rpc


@pytest_asyncio.fixture
async def ws_context() -> AsyncGenerator[WsServer, None]:
    """Fixture for a WsServer."""
    mock = MagicMock(spec=WsServer)

    yield mock


@pytest_asyncio.fixture
async def rpc_device(
    client_session: ClientSession, ws_context: WsServer, ws_rpc: WsRPCMocker
) -> AsyncGenerator[RpcDevice, None]:
    """Fixture for RpcDevice."""
    await ws_rpc.disconnect()

    options = ConnectionOptions(
        "10.10.10.10",
        "username",
        "password",
    )

    rpc_device = await RpcDevice.create(client_session, ws_context, options)
    rpc_device._wsrpc = ws_rpc
    rpc_device.call_rpc_multiple = AsyncMock()

    yield rpc_device
