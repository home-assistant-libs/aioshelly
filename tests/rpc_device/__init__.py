"""Tests for RPC device."""

import asyncio
import pathlib
from typing import Any

from orjson import loads


def get_device_fixture_path(device: str, filename: str) -> pathlib.Path:
    """Get path of a device fixture."""
    return pathlib.Path(__file__).parent.joinpath("fixtures", device, filename)


async def load_device_fixture(device: str, filename: str) -> dict[str, Any]:
    """Load a device fixture."""
    fixture_path = get_device_fixture_path(device, filename)
    json_bytes = await asyncio.get_running_loop().run_in_executor(
        None, fixture_path.read_bytes
    )
    return loads(json_bytes)
