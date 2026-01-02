"""Tests for Block device."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest_asyncio
from aiohttp.client import ClientSession

import aioshelly.block_device.device as device_module
from aioshelly.block_device import BlockDevice


@pytest_asyncio.fixture
async def client_session() -> AsyncGenerator[ClientSession, None]:
    """Fixture for a ClientSession."""
    return MagicMock(spec=ClientSession)


@pytest_asyncio.fixture
async def mock_block_device() -> AsyncGenerator[BlockDevice, None]:
    """Fixture for a mock block device."""
    # Create a fake BlockDevice instance
    fake_block = device_module.BlockDevice.__new__(device_module.BlockDevice)
    yield fake_block
