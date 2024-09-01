"""Tests for RPC device."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from aiohttp.client import ClientSession
from aiohttp.client_ws import ClientWebSocketResponse
from aiohttp.http_websocket import WSMessage

from aioshelly.rpc_device.wsrpc import RPCSource, WsRPC


class ResponseMocker:
    """Mocker for a WebSocket responses."""

    def __init__(self) -> None:
        """Initialize the mocker."""
        self.queue = asyncio.Queue()

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
) -> AsyncGenerator[WsRPC, None]:
    """Fixture for an RPC WebSocket."""
    with patch("aioshelly.rpc_device.wsrpc.ClientWebSocketResponse") as mock:
        mock.return_value = rpc_websocket_response
        ws_rpc = WsRPC("127.0.0.1", notify_history.save)
        await ws_rpc.connect(client_session)
        yield ws_rpc
        await ws_rpc.disconnect()
