"""Tests for rpc_device.device module."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio

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


@pytest_asyncio.fixture
async def blu_gateway_device_info() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for BLU Gateway Gen3 device info."""
    yield await load_device_fixture("shellyblugatewaygen3", "Shelly.GetDeviceInfo")


@pytest_asyncio.fixture
async def blu_gateway_config() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for BLU Gateway Gen3 config."""
    yield await load_device_fixture("shellyblugatewaygen3", "Shelly.GetConfig")


@pytest_asyncio.fixture
async def blu_gateway_status() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for BLU Gateway Gen3 status."""
    yield await load_device_fixture("shellyblugatewaygen3", "Shelly.GetStatus")


@pytest_asyncio.fixture
async def blu_gateway_components() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for BLU Gateway Gen3 components."""
    yield await load_device_fixture("shellyblugatewaygen3", "Shelly.GetComponents")


@pytest_asyncio.fixture
async def blu_gateway_remote_config() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for BLU Gateway Gen3 remote config."""
    yield await load_device_fixture("shellyblugatewaygen3", "BluTrv.GetRemoteConfig")


def test_mergedicts() -> None:
    """Test the recursive dict merge."""
    dest = {"a": 1, "b": {"c": 2, "d": 3}}
    source = {"b": {"c": 4, "e": 5}}
    mergedicts(dest, source)
    assert dest == {"a": 1, "b": {"c": 4, "d": 3, "e": 5}}


@pytest.mark.asyncio
async def test_parse_dynamic_components(rpc_device: RpcDevice) -> None:
    """Test RPC device _parse_dynamic_components() method."""
    rpc_device._status = {"ble": {}}
    rpc_device._config = {"ble": {"enable": True}}

    rpc_device._parse_dynamic_components(
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

    assert rpc_device._status["number:200"] == VIRT_COMP_STATUS
    assert rpc_device._config["number:200"] == VIRT_COMP_CONFIG


@pytest.mark.asyncio
async def test_parse_dynamic_components_with_attrs(rpc_device: RpcDevice) -> None:
    """Test RPC device _parse_dynamic_components() method with attrs."""
    rpc_device._status = {"ble": {}}
    rpc_device._config = {"ble": {"enable": True}}

    rpc_device._parse_dynamic_components(
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

    assert rpc_device._status["number:200"] == VIRT_COMP_STATUS
    assert rpc_device._config["number:200"] == {**VIRT_COMP_CONFIG, **VIRT_COMP_ATTRS}


@pytest.mark.asyncio
async def test_parse_dynamic_components_not_initialized(rpc_device: RpcDevice) -> None:
    """Test RPC device _parse_dynamic_components method with not initialized device."""
    with pytest.raises(NotInitialized):
        rpc_device._parse_dynamic_components({"lorem": "ipsum"})


@pytest.mark.asyncio
async def test_retrieve_blutrv_components_wrong_device(rpc_device: RpcDevice) -> None:
    """Test _retrieve_blutrv_components method with wrong device."""
    rpc_device._shelly = {"model": "Some Shelly device"}

    await rpc_device._retrieve_blutrv_components({"lorem": "ipsum"})


@pytest.mark.asyncio
async def test_retrieve_blutrv_components_not_initialized(
    rpc_device: RpcDevice,
) -> None:
    """Test _retrieve_blutrv_components method with not initialized device."""
    rpc_device._shelly = {"model": "S3GW-1DBT001"}

    with pytest.raises(NotInitialized):
        await rpc_device._retrieve_blutrv_components({"lorem": "ipsum"})


@pytest.mark.parametrize(
    ("firmware", "expected"),
    [
        ("20250203-144328/1.5.0-beta2-gbf89ed5", True),
        ("20231209-144328/1.0.0-gbf89ed5", False),
        ("lorem-ipsum", False),
    ],
)
@pytest.mark.asyncio
async def test_supports_dynamic_components(
    rpc_device: RpcDevice, firmware: str, expected: bool
) -> None:
    """Test _supports_dynamic_components method with not initialized device."""
    rpc_device._shelly = {"model": "Some Model", "fw_id": firmware}

    assert rpc_device._supports_dynamic_components() is expected


@pytest.mark.asyncio
async def test_get_dynamic_components(
    rpc_device: RpcDevice,
    blu_gateway_device_info: dict[str, Any],
    blu_gateway_config: dict[str, Any],
    blu_gateway_status: dict[str, Any],
    blu_gateway_remote_config: dict[str, Any],
    blu_gateway_components: dict[str, Any],
) -> None:
    """Test get_dynamic_components method."""
    rpc_device.initialized = True
    rpc_device._shelly = blu_gateway_device_info
    rpc_device._config = blu_gateway_config
    rpc_device._status = blu_gateway_status
    rpc_device.call_rpc_multiple.side_effect = [
        [blu_gateway_components],
        [blu_gateway_remote_config],
    ]

    await rpc_device.get_dynamic_components()

    assert rpc_device.call_rpc_multiple.call_count == 2
    assert (
        rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "BluTrv.GetRemoteConfig"
    )
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"id": 200}

    assert rpc_device.config["blutrv:200"]["local_name"] == "SBTR-001AEU"
    assert rpc_device.config["blutrv:200"]["name"] == "Shelly BLU TRV [DDEEFF]"
    assert rpc_device.config["blutrv:200"]["addr"] == "aa:bb:cc:dd:ee:ff"
    assert rpc_device.config["blutrv:200"]["enable"] is True

    assert rpc_device.status["blutrv:200"]["current_C"] == 21
    assert rpc_device.status["blutrv:200"]["target_C"] == 19
    assert rpc_device.status["blutrv:200"]["pos"] == 0
    assert rpc_device.status["blutrv:200"]["rssi"] == -58
    assert rpc_device.status["blutrv:200"]["errors"] == []


@pytest.mark.asyncio
async def test_get_dynamic_components_not_supported(rpc_device: RpcDevice) -> None:
    """Test get_dynamic_components method when dynamic components are not supported."""
    rpc_device.initialized = True
    rpc_device._shelly = {"fw_id": "20231209-144328/1.0.0-gbf89ed5"}

    await rpc_device.get_dynamic_components()

    assert rpc_device._dynamic_components == []


@pytest.mark.asyncio
async def test_device_initialize(
    rpc_device: RpcDevice,
    blu_gateway_device_info: dict[str, Any],
    blu_gateway_config: dict[str, Any],
    blu_gateway_status: dict[str, Any],
    blu_gateway_remote_config: dict[str, Any],
    blu_gateway_components: dict[str, Any],
) -> None:
    """Test RpcDevice initialize method."""
    rpc_device.call_rpc_multiple.side_effect = [
        [blu_gateway_device_info],
        [blu_gateway_config, blu_gateway_status, blu_gateway_components],
        [blu_gateway_remote_config],
    ]

    await rpc_device.initialize()

    assert rpc_device.connected is True
    assert rpc_device.firmware_supported is True
    assert rpc_device.name == "Test Name"
    assert rpc_device.hostname == "shellyblugwg3-aabbccddeeff"
    assert rpc_device.version == "1.5.0-beta2"
    assert rpc_device.gen == 3
    assert rpc_device.last_error is None
    assert rpc_device.xmod_info == {}
    assert rpc_device.requires_auth is True
