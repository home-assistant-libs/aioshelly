"""Tests for Block device."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest_asyncio
from aiohttp.client import ClientSession


@pytest_asyncio.fixture
async def client_session() -> AsyncGenerator[ClientSession, None]:
    """Fixture for a ClientSession."""
    return MagicMock(spec=ClientSession)
