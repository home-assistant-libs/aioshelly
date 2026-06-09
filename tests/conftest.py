"""Shared test fixtures."""

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def aiohttp_json_response_ctx() -> Any:
    """Return a factory for an async request context manager with JSON payload."""

    def _factory(payload: dict[str, Any]) -> AsyncMock:
        response = AsyncMock()
        response.json.return_value = payload
        request_ctx = AsyncMock()
        request_ctx.__aenter__.return_value = response
        return request_ctx

    return _factory
