"""Tests for rpc_device.device module."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from aiohttp import ClientError
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ServerDisconnectedError

from aioshelly.common import ConnectionOptions
from aioshelly.const import NOTIFY_WS_CLOSED
from aioshelly.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
    NotInitialized,
    RpcCallError,
)
from aioshelly.rpc_device.device import RpcDevice, RpcUpdateType, mergedicts
from aioshelly.rpc_device.wsrpc import RPCSource, WsRPC, WsServer

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
WEBSOCKET_URL = "ws://10.10.10.10:8123/api/shelly/ws"


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


@pytest_asyncio.fixture
async def mini_1_g4_device_info() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for Mini 1 Gen4 device info."""
    yield await load_device_fixture("shellymini1gen4", "Shelly.GetDeviceInfo")


@pytest_asyncio.fixture
async def mini_1_g4_config() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for Mini 1 Gen4 config."""
    yield await load_device_fixture("shellymini1gen4", "Shelly.GetConfig")


@pytest_asyncio.fixture
async def mini_1_g4_status() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for Mini 1 Gen4 status."""
    yield await load_device_fixture("shellymini1gen4", "Shelly.GetStatus")


@pytest_asyncio.fixture
async def mini_1_g4_components() -> AsyncGenerator[dict[str, Any], None]:
    """Fixture for Mini 1 Gen4 components."""
    yield await load_device_fixture("shellymini1gen4", "Shelly.GetComponents")


def test_mergedicts() -> None:
    """Test the recursive dict merge."""
    dest = {"a": 1, "b": {"c": 2, "d": 3}}
    source = {"b": {"c": 4, "e": 5}}
    mergedicts(dest, source)
    assert dest == {"a": 1, "b": {"c": 4, "d": 3, "e": 5}}


def test_mergedicts_to_none() -> None:
    """Test merge a dict to a None."""
    # transition is None in dest
    dest = {
        "ts": 1740607224.75,
        "light:0": {
            "id": 0,
            "brightness": 0,
            "output": False,
            "source": "transition",
            "transition": None,
        },
        "sensor:0": {"id": 0, "temperature": 0},
    }
    # transition is dict in source
    source = {
        "ts": 1740607225.26,
        "light:0": {
            "id": 0,
            "brightness": 0,
            "output": False,
            "source": "HTTP_in",
            "transition": {
                "duration": 0.5,
                "started_at": 1740607225.26,
                "target": {"brightness": 0, "output": False},
            },
        },
    }

    mergedicts(dest, source)

    assert dest == {
        "ts": 1740607225.26,
        "light:0": {
            "id": 0,
            "brightness": 0,
            "output": False,
            "source": "HTTP_in",
            "transition": {
                "duration": 0.5,
                "started_at": 1740607225.26,
                "target": {"brightness": 0, "output": False},
            },
        },
        "sensor:0": {"id": 0, "temperature": 0},
    }


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
async def test_supports_dynamic_components_sleeping_device(
    rpc_device: RpcDevice,
) -> None:
    """Test _supports_dynamic_components method with a sleeping device."""
    rpc_device._shelly = {
        "model": "Some Model",
        "fw_id": "20250203-144328/1.5.0-beta2-gbf89ed5",
    }
    rpc_device._status = {"sys": {"wakeup_period": 60}}

    assert rpc_device._supports_dynamic_components() is False


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
async def test_shelly_gen1(client_session: ClientSession, ws_context: WsServer) -> None:
    """Test Shelly Gen1 device."""
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    rpc_device = await RpcDevice.create(client_session, ws_context, options)
    rpc_device._wsrpc = AsyncMock(spec=WsRPC)
    rpc_device._wsrpc.connect.side_effect = ServerDisconnectedError

    with pytest.raises(DeviceConnectionError):
        await rpc_device.initialize()


@pytest.mark.asyncio
async def test_device_initialize_and_shutdown(
    rpc_device: RpcDevice,
    blu_gateway_device_info: dict[str, Any],
    blu_gateway_config: dict[str, Any],
    blu_gateway_status: dict[str, Any],
    blu_gateway_remote_config: dict[str, Any],
    blu_gateway_components: dict[str, Any],
) -> None:
    """Test RpcDevice initialize and shutdown methods."""
    rpc_device.call_rpc_multiple.side_effect = [
        [blu_gateway_device_info],
        [blu_gateway_config, blu_gateway_status, blu_gateway_components],
        [blu_gateway_remote_config],
    ]
    rpc_device.subscribe_updates(Mock())

    await rpc_device.initialize()

    assert rpc_device._update_listener is not None
    assert rpc_device._unsub_ws is not None
    assert rpc_device.connected is True
    assert rpc_device.firmware_supported is True
    assert rpc_device.name == "Test Name"
    assert rpc_device.hostname == "shellyblugwg3-aabbccddeeff"
    assert rpc_device.version == "1.5.0-beta2"
    assert rpc_device.gen == 3
    assert rpc_device.last_error is None
    assert rpc_device.xmod_info == {}
    assert rpc_device.requires_auth is True
    assert rpc_device.zigbee_enabled is False
    assert rpc_device.zigbee_firmware is False

    await rpc_device.shutdown()

    assert rpc_device._update_listener is None
    assert rpc_device._unsub_ws is None


@pytest.mark.asyncio
async def test_device_initialize_lock(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice initialize."""
    rpc_device._initialize_lock = Mock(locked=Mock(return_value=True))

    with pytest.raises(RuntimeError):
        await rpc_device.initialize()


@pytest.mark.asyncio
async def test_device_already_initialized(
    rpc_device: RpcDevice,
    blu_gateway_device_info: dict[str, Any],
    blu_gateway_config: dict[str, Any],
    blu_gateway_status: dict[str, Any],
    blu_gateway_remote_config: dict[str, Any],
    blu_gateway_components: dict[str, Any],
) -> None:
    """Test RpcDevice initialize."""
    rpc_device.call_rpc_multiple.side_effect = [
        [blu_gateway_device_info],
        [blu_gateway_config, blu_gateway_status, blu_gateway_components],
        [blu_gateway_remote_config],
    ]
    rpc_device._wsrpc = AsyncMock(spec=WsRPC)

    await rpc_device.initialize()

    assert rpc_device.initialized is True
    assert rpc_device.status is not None

    rpc_device.call_rpc_multiple.side_effect = [
        [blu_gateway_device_info],
        [blu_gateway_config, blu_gateway_status, blu_gateway_components],
        [blu_gateway_remote_config],
    ]

    # call initialize() once again
    await rpc_device.initialize()

    assert rpc_device.initialized is True
    assert rpc_device.status is not None


@pytest.mark.parametrize(
    ("exc", "result_exc", "result_str"),
    [
        (InvalidAuthError, InvalidAuthError, ""),
        (RpcCallError(404, "test error"), DeviceConnectionError, "test error"),
        (ClientError, DeviceConnectionError, ""),
        (DeviceConnectionError, DeviceConnectionError, ""),
        (OSError, DeviceConnectionError, ""),
    ],
)
@pytest.mark.asyncio
async def test_device_exception_on_init(
    client_session: ClientSession,
    ws_context: WsServer,
    blu_gateway_device_info: dict[str, Any],
    exc: Exception,
    result_exc: Exception,
    result_str: str,
) -> None:
    """Test RpcDevice initialize with an exception."""
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    rpc_device = await RpcDevice.create(client_session, ws_context, options)
    rpc_device._wsrpc = AsyncMock(spec=WsRPC)
    rpc_device._wsrpc.calls.side_effect = [[blu_gateway_device_info], exc]

    with pytest.raises(result_exc, match=result_str):
        await rpc_device.initialize()


@pytest.mark.asyncio
async def test_device_not_initialized(rpc_device: RpcDevice) -> None:
    """Test RpcDevice not initialized."""
    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "gen")

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "shelly")

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "config")

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "status")

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "event")

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "zigbee_enabled")


@pytest.mark.asyncio
async def test_update_outbound_websocket(rpc_device: RpcDevice) -> None:
    """Test RpcDevice update_outbound_websocket method."""
    result = await rpc_device.update_outbound_websocket(WEBSOCKET_URL)

    assert result is True
    assert rpc_device.call_rpc_multiple.call_count == 3
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Ws.GetConfig"
    assert call_args_list[1][0][0][0][0] == "Ws.SetConfig"
    assert call_args_list[2][0][0][0][0] == "Shelly.Reboot"


@pytest.mark.asyncio
async def test_update_outbound_websocket_not_needed(rpc_device: RpcDevice) -> None:
    """Test RpcDevice update_outbound_websocket method."""
    rpc_device.call_rpc_multiple.side_effect = [
        [{"enable": True, "server": WEBSOCKET_URL}]
    ]

    result = await rpc_device.update_outbound_websocket(WEBSOCKET_URL)

    assert result is False
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Ws.GetConfig"


@pytest.mark.asyncio
async def test_update_outbound_websocket_restart_not_needed(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice update_outbound_websocket method."""
    rpc_device.call_rpc_multiple.side_effect = [
        [{"enable": False}],
        [{"restart_required": False}],
    ]

    result = await rpc_device.update_outbound_websocket(WEBSOCKET_URL)

    assert result is False
    assert rpc_device.call_rpc_multiple.call_count == 2
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Ws.GetConfig"
    assert call_args_list[1][0][0][0][0] == "Ws.SetConfig"


@pytest.mark.asyncio
async def test_ble_getconfig(rpc_device: RpcDevice) -> None:
    """Test RpcDevice ble_getconfig method."""
    rpc_device.call_rpc_multiple.return_value = [
        {"enable": True, "rpc": {"enable": True}}
    ]

    result = await rpc_device.ble_getconfig()

    assert result == {"enable": True, "rpc": {"enable": True}}
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "BLE.GetConfig"


@pytest.mark.asyncio
async def test_ble_setconfig(rpc_device: RpcDevice) -> None:
    """Test RpcDevice ble_setconfig method."""
    await rpc_device.ble_setconfig(True, True)

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "BLE.SetConfig"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {
        "config": {"enable": True, "rpc": {"enable": True}}
    }


@pytest.mark.asyncio
async def test_script_stop(rpc_device: RpcDevice) -> None:
    """Test RpcDevice script_stop method."""
    await rpc_device.script_stop(12)

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.Stop"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"id": 12}


@pytest.mark.asyncio
async def test_script_start(rpc_device: RpcDevice) -> None:
    """Test RpcDevice script_start method."""
    await rpc_device.script_start(11)

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.Start"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"id": 11}


@pytest.mark.asyncio
async def test_script_create(rpc_device: RpcDevice) -> None:
    """Test RpcDevice script_create method."""
    await rpc_device.script_create("test_script")

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.Create"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"name": "test_script"}


@pytest.mark.asyncio
async def test_script_putcode(rpc_device: RpcDevice) -> None:
    """Test RpcDevice script_putcode method."""
    await rpc_device.script_putcode(9, "lorem ipsum")

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.PutCode"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {
        "id": 9,
        "code": "lorem ipsum",
    }


@pytest.mark.asyncio
async def test_script_getcode(rpc_device: RpcDevice) -> None:
    """Test RpcDevice script_getcode method."""
    rpc_device.call_rpc_multiple.return_value = [{"data": "super duper script"}]

    result = await rpc_device.script_getcode(8)

    assert result == {"data": "super duper script"}
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.GetCode"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"id": 8, "offset": 0}


@pytest.mark.asyncio
async def test_script_list(rpc_device: RpcDevice) -> None:
    """Test RpcDevice script_list method."""
    rpc_device.call_rpc_multiple.return_value = [
        {
            "scripts": [
                {"id": 1, "name": "my_script", "enable": False, "running": True},
            ]
        }
    ]

    result = await rpc_device.script_list()

    assert result == [{"id": 1, "name": "my_script", "enable": False, "running": True}]
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.List"


@pytest.mark.asyncio
async def test_get_all_pages(rpc_device: RpcDevice) -> None:
    """Test RpcDevice get_all_pages method."""
    rpc_device.call_rpc_multiple.return_value = [
        {"total": 2, "components": [{"key": "component2"}]}
    ]

    result = await rpc_device.get_all_pages(
        {"total": 2, "components": [{"key": "component1"}]}
    )

    assert result == {
        "total": 2,
        "components": [{"key": "component1"}, {"key": "component2"}],
    }
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Shelly.GetComponents"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {
        "dynamic_only": True,
        "offset": 1,
    }


@pytest.mark.asyncio
async def test_on_notification_ws_closed(rpc_device: RpcDevice) -> None:
    """Test RpcDevice _on_notification method when WS is closed."""
    rpc_device._update_listener = Mock()
    rpc_device.initialized = True

    rpc_device._on_notification(RPCSource.CLIENT, NOTIFY_WS_CLOSED)

    assert rpc_device._update_listener.call_count == 1
    assert rpc_device._update_listener.call_args[0][1] is RpcUpdateType.DISCONNECTED


@pytest.mark.asyncio
async def test_on_notification_notify_full_status(rpc_device: RpcDevice) -> None:
    """Test RpcDevice _on_notification method with NotifyFullStatus."""
    rpc_device._update_listener = Mock()
    rpc_device.initialized = True

    rpc_device._on_notification(RPCSource.CLIENT, "NotifyFullStatus", {"test": True})

    assert rpc_device._update_listener.call_count == 1
    assert rpc_device._update_listener.call_args[0][1] is RpcUpdateType.STATUS
    assert rpc_device.status == {"test": True}


@pytest.mark.asyncio
async def test_on_notification_notify_status(rpc_device: RpcDevice) -> None:
    """Test RpcDevice _on_notification method with NotifyStatus."""
    rpc_device._update_listener = Mock()
    rpc_device.initialized = True
    rpc_device._status = {"sys": {}}

    rpc_device._on_notification(RPCSource.CLIENT, "NotifyStatus", {"test": True})

    assert rpc_device._update_listener.call_count == 1
    assert rpc_device._update_listener.call_args[0][1] is RpcUpdateType.STATUS
    assert rpc_device.status == {"sys": {}, "test": True}


@pytest.mark.asyncio
async def test_on_notification_notify_event(rpc_device: RpcDevice) -> None:
    """Test RpcDevice _on_notification method with NotifyEvent."""
    rpc_device._update_listener = Mock()
    rpc_device.initialized = True

    rpc_device._on_notification(RPCSource.CLIENT, "NotifyEvent", {"test": True})

    assert rpc_device._update_listener.call_count == 1
    assert rpc_device._update_listener.call_args[0][1] is RpcUpdateType.EVENT
    assert rpc_device.event == {"test": True}


@pytest.mark.asyncio
async def test_on_notification_battery_device_online(rpc_device: RpcDevice) -> None:
    """Test RpcDevice _on_notification method with RpcUpdateType.ONLINE."""
    rpc_device._update_listener = Mock()

    rpc_device._on_notification(RPCSource.SERVER, "NotifyStatus", {"test": True})

    assert rpc_device._update_listener.call_count == 1
    assert rpc_device._update_listener.call_args[0][1] is RpcUpdateType.ONLINE


@pytest.mark.asyncio
async def test_on_notification_no_listener(rpc_device: RpcDevice) -> None:
    """Test RpcDevice _on_notification without listener."""
    # no listener
    rpc_device._update_listener = Mock()
    rpc_device._update_listener.__bool__ = lambda _: False

    rpc_device._on_notification(RPCSource.SERVER, "NotifyStatus", {"test": True})

    rpc_device._update_listener.assert_not_called()

    # add listener and verify it is called
    update_listener = Mock()
    rpc_device.subscribe_updates(update_listener)

    rpc_device._on_notification(RPCSource.SERVER, "NotifyStatus", {"test": True})

    assert update_listener.call_count == 1
    assert update_listener.call_args[0][1] is RpcUpdateType.ONLINE


@pytest.mark.asyncio
async def test_device_mac_address_mismatch(
    client_session: ClientSession,
    ws_context: WsServer,
    blu_gateway_device_info: dict[str, Any],
) -> None:
    """Test RpcDevice initialize method."""
    options = ConnectionOptions("10.10.10.10", device_mac="112233445566")

    rpc_device = await RpcDevice.create(client_session, ws_context, options)
    rpc_device.call_rpc_multiple = AsyncMock()

    rpc_device.call_rpc_multiple.return_value = [blu_gateway_device_info]

    with pytest.raises(MacAddressMismatchError):
        await rpc_device.initialize()


@pytest.mark.asyncio
async def test_poll(
    rpc_device: RpcDevice,
    blu_gateway_device_info: dict[str, Any],
    blu_gateway_status: dict[str, Any],
    blu_gateway_remote_config: dict[str, Any],
    blu_gateway_components: dict[str, Any],
) -> None:
    """Test RpcDevice poll method."""
    rpc_device.call_rpc_multiple.side_effect = [
        [blu_gateway_status, blu_gateway_components],
        [blu_gateway_remote_config],
    ]
    rpc_device._shelly = blu_gateway_device_info
    rpc_device._status = {"lorem": "ipsum"}
    rpc_device._config = {"lorem": "ipsum"}
    rpc_device._dynamic_components = [{"key": "component1"}]

    await rpc_device.poll()

    assert rpc_device.call_rpc_multiple.call_count == 2
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Shelly.GetStatus"
    assert call_args_list[0][0][0][1][0] == "Shelly.GetComponents"
    assert call_args_list[1][0][0][0][0] == "BluTrv.GetRemoteConfig"


@pytest.mark.asyncio
async def test_poll_not_initialized(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice poll method when NotInitialized."""
    with pytest.raises(NotInitialized):
        await rpc_device.poll()


@pytest.mark.asyncio
async def test_poll_call_error(
    rpc_device: RpcDevice,
    blu_gateway_status: dict[str, Any],
) -> None:
    """Test RpcDevice poll method when RpcCallError."""
    rpc_device.call_rpc_multiple.return_value = [None]

    with pytest.raises(RpcCallError, match="empty response to Shelly.GetStatus"):
        await rpc_device.poll()

    rpc_device.call_rpc_multiple.return_value = [blu_gateway_status, None]
    rpc_device._dynamic_components = [{"key": "component1"}]
    rpc_device._status = {"lorem": "ipsum"}

    with pytest.raises(RpcCallError, match="empty response to Shelly.GetComponents"):
        await rpc_device.poll()


@pytest.mark.asyncio
async def test_update_config(rpc_device: RpcDevice) -> None:
    """Test RpcDevice update_config method."""
    await rpc_device.update_config()

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Shelly.GetConfig"


@pytest.mark.asyncio
async def test_update_status(rpc_device: RpcDevice) -> None:
    """Test RpcDevice update_status method."""
    await rpc_device.update_status()

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Shelly.GetStatus"


@pytest.mark.asyncio
async def test_trigger_ota_update(rpc_device: RpcDevice) -> None:
    """Test RpcDevice trigger_ota_update method."""
    await rpc_device.trigger_ota_update(beta=True)

    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Shelly.Update"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {"stage": "beta"}


@pytest.mark.asyncio
async def test_incorrect_shutdown(
    client_session: ClientSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multiple shutdown calls at incorrect order.

    https://github.com/home-assistant-libs/aioshelly/pull/535
    """
    ws_context = WsServer()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    rpc_device1 = await RpcDevice.create(client_session, ws_context, options)
    rpc_device2 = await RpcDevice.create(client_session, ws_context, options)

    # shutdown for device2 remove subscription for device1 from ws_context
    await rpc_device2.shutdown()

    assert "error during shutdown: KeyError('AABBCCDDEEFF')" not in caplog.text

    await rpc_device1.shutdown()

    assert "error during shutdown: KeyError('AABBCCDDEEFF')" in caplog.text


@pytest.mark.parametrize(
    ("side_effect", "supports_scripts"),
    [
        (RpcCallError(-105, "Argument 'id', value 1 not found!"), True),
        (RpcCallError(-114, "Method Script.GetCode failed: Method not found!"), False),
        (RpcCallError(404, "No handler for Script.GetCode"), False),
        (
            [
                {
                    "id": 5,
                    "src": "shellyplus2pm-a8032ab720ac",
                    "dst": "aios-2293750469632",
                    "result": {"data": "script"},
                }
            ],
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_supports_scripts(
    rpc_device: RpcDevice,
    side_effect: Exception | dict[str, Any],
    supports_scripts: bool,
) -> None:
    """Test supports_scripts method."""
    rpc_device.call_rpc_multiple.side_effect = [side_effect]

    result = await rpc_device.supports_scripts()

    assert result == supports_scripts
    assert rpc_device.call_rpc_multiple.call_count == 1
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][0] == "Script.GetCode"
    assert rpc_device.call_rpc_multiple.call_args[0][0][0][1] == {
        "id": 1,
        "len": 0,
        "offset": 0,
    }


@pytest.mark.asyncio
async def test_supports_scripts_raises_unkown_errors(rpc_device: RpcDevice) -> None:
    """Test supports_scripts raises for unknown errors."""
    message = "Missing required argument 'id'!"
    rpc_device.call_rpc_multiple.side_effect = [RpcCallError(-103, message)]

    with pytest.raises(RpcCallError, match=message):
        await rpc_device.supports_scripts()


@pytest.mark.asyncio
async def test_trigger_blu_trv_calibration(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice trigger_blu_trv_calibration() method."""
    await rpc_device.trigger_blu_trv_calibration(200)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.Calibrate",
        "params": {"id": 0},
    }
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_blu_trv_set_target_temperature(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice blu_trv_set_target_temperature() method."""
    await rpc_device.blu_trv_set_target_temperature(200, 21.5)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.SetTarget",
        "params": {"id": 0, "target_C": 21.5},
    }
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_blu_trv_set_external_temperature(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice blu_trv_set_external_temperature() method."""
    await rpc_device.blu_trv_set_external_temperature(200, 22.6)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.SetExternalTemperature",
        "params": {"id": 0, "t_C": 22.6},
    }
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_blu_trv_set_valve_position(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice blu_trv_set_valve_position() method."""
    await rpc_device.blu_trv_set_valve_position(200, 55.0)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.SetPosition",
        "params": {"id": 0, "pos": 55},
    }
    # the valve position value should be an integer
    assert isinstance(call_args_list[0][0][0][0][1]["params"]["pos"], int)
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_blu_trv_set_boost(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice blu_trv_set_boost() method."""
    await rpc_device.blu_trv_set_boost(200)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.SetBoost",
        "params": {"id": 0},
    }
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_blu_trv_set_boost_duration(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice blu_trv_set_boost() method with duration."""
    await rpc_device.blu_trv_set_boost(200, 33)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.SetBoost",
        "params": {"id": 0, "duration": 33},
    }
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_blu_trv_clear_boost(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice blu_trv_clear_boost() method."""
    await rpc_device.blu_trv_clear_boost(200)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "BluTRV.Call"
    assert call_args_list[0][0][0][0][1] == {
        "id": 200,
        "method": "Trv.ClearBoost",
        "params": {"id": 0},
    }
    assert call_args_list[0][0][1] == 60


@pytest.mark.asyncio
async def test_number_set(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice number_set() method."""
    await rpc_device.number_set(12, 33.2)

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Number.Set"
    assert call_args_list[0][0][0][0][1] == {
        "id": 12,
        "value": 33.2,
    }


@pytest.mark.asyncio
async def test_button_trigger(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice button_trigger() method."""
    await rpc_device.button_trigger(12, "single_push")

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Button.Trigger"
    assert call_args_list[0][0][0][0][1] == {
        "id": 12,
        "event": "single_push",
    }


@pytest.mark.asyncio
async def test_enum_set(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice enum_set() method."""
    await rpc_device.enum_set(12, "option 1")

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Enum.Set"
    assert call_args_list[0][0][0][0][1] == {
        "id": 12,
        "value": "option 1",
    }


@pytest.mark.asyncio
async def test_text_set(
    rpc_device: RpcDevice,
) -> None:
    """Test RpcDevice text_set() method."""
    await rpc_device.text_set(12, "lorem ipsum")

    assert rpc_device.call_rpc_multiple.call_count == 1
    call_args_list = rpc_device.call_rpc_multiple.call_args_list
    assert call_args_list[0][0][0][0][0] == "Text.Set"
    assert call_args_list[0][0][0][0][1] == {
        "id": 12,
        "value": "lorem ipsum",
    }


@pytest.mark.asyncio
async def test_device_gen4_zigbee(
    rpc_device: RpcDevice,
    mini_1_g4_device_info: dict[str, Any],
    mini_1_g4_config: dict[str, Any],
    mini_1_g4_status: dict[str, Any],
    mini_1_g4_components: dict[str, Any],
) -> None:
    """Test RpcDevice initialize and shutdown methods."""
    rpc_device.call_rpc_multiple.side_effect = [
        [mini_1_g4_device_info],
        [mini_1_g4_config, mini_1_g4_status, mini_1_g4_components],
    ]
    rpc_device.subscribe_updates(Mock())

    await rpc_device.initialize()

    assert rpc_device._update_listener is not None
    assert rpc_device._unsub_ws is not None
    assert rpc_device.connected is True
    assert rpc_device.firmware_supported is True
    assert rpc_device.name == "Shelly 1 Mini Gen4 [DDEEFF]"
    assert rpc_device.hostname == "shelly1minig4-aabbccddeeff"
    assert rpc_device.version == "1.5.99-g4prod1"
    assert rpc_device.gen == 4
    assert rpc_device.last_error is None
    assert rpc_device.xmod_info == {}
    assert rpc_device.requires_auth is False
    assert rpc_device.zigbee_enabled is True
    assert rpc_device.zigbee_firmware is True

    await rpc_device.shutdown()


@pytest.mark.asyncio
async def test_device_gen4_zigbee_disabled(
    rpc_device: RpcDevice,
    mini_1_g4_device_info: dict[str, Any],
    mini_1_g4_config: dict[str, Any],
    mini_1_g4_status: dict[str, Any],
    mini_1_g4_components: dict[str, Any],
) -> None:
    """Test RpcDevice with Zigbee firmware when Zigbee is disabled."""
    mini_1_g4_config["zigbee"] = {"enable": False}
    rpc_device.call_rpc_multiple.side_effect = [
        [mini_1_g4_device_info],
        [mini_1_g4_config, mini_1_g4_status, mini_1_g4_components],
    ]
    rpc_device.subscribe_updates(Mock())

    await rpc_device.initialize()

    assert rpc_device.zigbee_enabled is False
    assert rpc_device.zigbee_firmware is True

    await rpc_device.shutdown()


@pytest.mark.asyncio
async def test_zigbee_properties_not_initialized(
    rpc_device: RpcDevice,
    mini_1_g4_device_info: dict[str, Any],
) -> None:
    """Test RpcDevice not initialized when accessing zigbee properties."""
    rpc_device.initialized = True
    rpc_device._shelly = mini_1_g4_device_info

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "zigbee_enabled")

    with pytest.raises(NotInitialized):
        hasattr(rpc_device, "zigbee_firmware")
