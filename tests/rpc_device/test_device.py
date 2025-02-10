"""Tests for rpc_device.device module."""

from unittest.mock import AsyncMock, Mock

import pytest

from aioshelly.exceptions import NotInitialized
from aioshelly.rpc_device.device import RpcDevice, mergedicts

from . import load_device_fixture

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

    device._status = {"ble": {}}
    device._config = {"ble": {"enable": True}}

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

    device._status = {"ble": {}}
    device._config = {"ble": {"enable": True}}

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


@pytest.mark.asyncio
async def test_parse_dynamic_components_not_initialized() -> None:
    """Test RPC device _parse_dynamic_components method with not initialized device."""
    device = await RpcDevice.create(Mock(), Mock(), "10.10.10.10")

    with pytest.raises(NotInitialized):
        device._parse_dynamic_components({"lorem": "ipsum"})


@pytest.mark.asyncio
async def test_retrieve_blutrv_components() -> None:
    """Test _retrieve_blutrv_components method."""
    device = await RpcDevice.create(Mock(), Mock(), "10.10.10.10")

    device._config = await load_device_fixture(
        "shellyblugatewaygen3", "Shelly.GetConfig"
    )
    device._status = await load_device_fixture(
        "shellyblugatewaygen3", "Shelly.GetStatus"
    )
    device._shelly = await load_device_fixture("shellyblugatewaygen3", "shelly.json")
    device.initialized = True

    components = await load_device_fixture(
        "shellyblugatewaygen3", "Shelly.GetComponents"
    )
    remote_config = await load_device_fixture(
        "shellyblugatewaygen3", "BluTrv.GetRemoteConfig"
    )
    device.call_rpc = AsyncMock(return_value=remote_config)

    await device._retrieve_blutrv_components(components)

    assert device.call_rpc.assert_called_once
    assert device.call_rpc.call_args[0][0] == "BluTrv.GetRemoteConfig"
    assert device.call_rpc.call_args[0][1] == {"id": 200}

    assert device.config["blutrv:200"]["local_name"] == "SBTR-001AEU"
    assert device.config["blutrv:200"]["name"] == "Shelly BLU TRV [DDEEFF]"
    assert device.config["blutrv:200"]["addr"] == "aa:bb:cc:dd:ee:ff"
    assert device.config["blutrv:200"]["enable"] is True

    assert device.status["blutrv:200"]["current_C"] == 21
    assert device.status["blutrv:200"]["target_C"] == 19
    assert device.status["blutrv:200"]["pos"] == 0
    assert device.status["blutrv:200"]["rssi"] == -58
    assert device.status["blutrv:200"]["errors"] == []


@pytest.mark.asyncio
async def test_retrieve_blutrv_components_wrong_device() -> None:
    """Test _retrieve_blutrv_components method with wrong device."""
    device = await RpcDevice.create(Mock(), Mock(), "10.10.10.10")

    device._shelly = {"model": "Some Shelly device"}

    await device._retrieve_blutrv_components({"lorem": "ipsum"})


@pytest.mark.asyncio
async def test_retrieve_blutrv_components_not_initialized() -> None:
    """Test _retrieve_blutrv_components method with not initialized device."""
    device = await RpcDevice.create(Mock(), Mock(), "10.10.10.10")

    device._shelly = {"model": "S3GW-1DBT001"}

    with pytest.raises(NotInitialized):
        await device._retrieve_blutrv_components({"lorem": "ipsum"})
