"""Tests for rpc_device.device module."""

from unittest.mock import Mock

import pytest

from aioshelly.rpc_device.device import RpcDevice, mergedicts

VIRT_COMP_STATUS = {"value": 0}
VIRT_COMP_CONFIG = {
    "id": 200,
    "name": "Test",
    "min": 0,
    "max": 100,
    "meta": {"ui": {"view": "slider", "unit": "%", "step": 1}},
}
VIRT_COMP_ATTRS = {"role": "current_humidity"}


def test_mergedicts() -> None:
    """Test the recursive dict merge."""
    dest = {"a": 1, "b": {"c": 2, "d": 3}}
    source = {"b": {"c": 4, "e": 5}}
    mergedicts(dest, source)
    assert dest == {"a": 1, "b": {"c": 4, "d": 3, "e": 5}}


@pytest.mark.asyncio
async def test_parse_dynamic_components() -> None:
    """Test RPC device _parse_dynamic_components() method."""
    device = await RpcDevice.create(Mock(), Mock(), "10.10.10.10")

    device._status = {}
    device._config = {}

    device._parse_dynamic_components(
        {
            "components": [
                {
                    "key": "number:200",
                    "status": VIRT_COMP_STATUS,
                    "config": VIRT_COMP_CONFIG,
                }
            ]
        }
    )

    assert device._status["number:200"] == VIRT_COMP_STATUS
    assert device._config["number:200"] == VIRT_COMP_CONFIG


@pytest.mark.asyncio
async def test_parse_dynamic_components_with_attrs() -> None:
    """Test RPC device _parse_dynamic_components() method with attrs."""
    device = await RpcDevice.create(Mock(), Mock(), "10.10.10.10")

    device._status = {}
    device._config = {}

    device._parse_dynamic_components(
        {
            "components": [
                {
                    "key": "number:200",
                    "status": VIRT_COMP_STATUS,
                    "config": VIRT_COMP_CONFIG,
                    "attrs": VIRT_COMP_ATTRS,
                }
            ]
        }
    )

    assert device._status["number:200"] == VIRT_COMP_STATUS
    assert device._config["number:200"] == {**VIRT_COMP_CONFIG, **VIRT_COMP_ATTRS}
