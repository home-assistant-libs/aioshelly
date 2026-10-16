"""Tests for block_device.device module."""

import asyncio
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import ClientError, ClientResponseError
from aiohttp.client import ClientSession
from bleak.backends.device import BLEDevice

from aioshelly.block_device import COAP, BlockDevice
from aioshelly.block_device.coap import CoapType
from aioshelly.block_device.device import Block, BlockUpdateType, LightBlock
from aioshelly.common import ConnectionOptions
from aioshelly.const import MODEL_RGBW2
from aioshelly.exceptions import (
    CustomPortNotSupported,
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
    MacAddressMismatchError,
    NotInitialized,
    WrongShellyGen,
)

NEW_FIRMWARE = "20230913-112003/v1.14.0-gcb84623"
OLD_FIRMWARE = "20201128-092454/v1.9.0@57ac4ad8"
SHELLY_INFO = {"type": "SHSW-1", "fw": NEW_FIRMWARE, "auth": False}
SETTINGS = {"name": "Living Room", "device": {"hostname": "shelly1-AABBCC"}}
STATUS = {"uptime": 100}
COAP_D = {
    "blk": [
        {"I": 0, "D": "relay_0"},
        {"I": 1, "D": "device"},
    ],
    "sen": [
        {"I": 112, "T": "S", "D": "output", "L": 0},
        {"I": 9101, "T": "S", "D": "mode", "L": [0, 1]},
        {"I": 3104, "T": "T", "D": "deviceTemp", "U": "C", "L": 1},
    ],
}
COAP_S = {"G": [[0, 112, 1], [0, 9101, "relay"], [0, 3104, 40.5]]}
COAP_S_VALUES = {112: 1, 9101: "relay", 3104: 40.5}
GET_INFO = "aioshelly.block_device.device.get_info"


def _create_device(options: ConnectionOptions | None = None) -> BlockDevice:
    """Create a block device with mocked CoAP context and session."""
    coap_context = MagicMock(spec=COAP)
    coap_context.request = AsyncMock()
    return BlockDevice(
        coap_context,
        MagicMock(spec=ClientSession),
        options or ConnectionOptions("10.10.10.10"),
    )


def _mock_http(device: BlockDevice, responses: dict[str, Any]) -> AsyncMock:
    """Mock device HTTP responses by path."""

    async def _request(_method: str, url: Any, **_kwargs: Any) -> Mock:
        resp = Mock()
        resp.json = AsyncMock(return_value=responses[url.path.lstrip("/")])
        return resp

    device.aiohttp_session.request = AsyncMock(side_effect=_request)
    return device.aiohttp_session.request


def _mock_coap_replies(device: BlockDevice, payloads: dict[str, Any]) -> None:
    """Mock CoAP requests replying with payload by path."""

    async def _request(_ip: str, path: str) -> None:
        device._coap_message_received(
            Mock(payload=payloads[path], coap_type=CoapType.REPLY)
        )

    device.coap_context.request = AsyncMock(side_effect=_request)


def _initialized_device(
    settings: dict[str, Any] | None = None,
    options: ConnectionOptions | None = None,
) -> BlockDevice:
    """Create a device in initialized state with blocks."""
    device = _create_device(options)
    device._shelly = SHELLY_INFO
    device._settings = settings or SETTINGS
    device._status = STATUS
    device.initialized = True
    device._update_d(COAP_D)
    device._update_s(COAP_S, CoapType.REPLY)
    return device


@pytest.mark.asyncio
async def test_incorrect_shutdown(
    client_session: ClientSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multiple shutdown calls at incorrect order.

    https://github.com/home-assistant-libs/aioshelly/pull/535
    """
    coap_context = COAP()
    coap_context.sock = Mock(spec=socket.socket)
    coap_context.transport = Mock(spec=asyncio.DatagramTransport)
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device1 = await BlockDevice.create(client_session, coap_context, options)
    block_device2 = await BlockDevice.create(client_session, coap_context, options)

    # shutdown for device2 remove subscription for device1 from ws_context
    await block_device2.shutdown()

    assert "error during shutdown: KeyError('DDEEFF')" not in caplog.text

    await block_device1.shutdown()

    assert "error during shutdown: KeyError('DDEEFF')" in caplog.text


def test_block_device_requires_ip_address(client_session: ClientSession) -> None:
    """Test that BlockDevice requires ip_address."""
    coap_context = COAP()
    ble_device = MagicMock(spec=BLEDevice)
    options = ConnectionOptions(ble_device=ble_device)

    with pytest.raises(ValueError, match="Block devices require ip_address"):
        BlockDevice(coap_context, client_session, options)


@pytest.mark.asyncio
async def test_block_device_ip_address_property_guard(
    client_session: ClientSession,
) -> None:
    """Test ip_address property guard when ip_address is None."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")

    block_device = BlockDevice(coap_context, client_session, options)

    # Manually set ip_address to None to test the property guard
    # This shouldn't happen in normal operation due to __init__ check
    block_device.options.ip_address = None

    with pytest.raises(RuntimeError, match="Block device ip_address is None"):
        _ = block_device.ip_address


@pytest.mark.asyncio
async def test_configure_coiot_protocol_sends_correct_parameters(
    mock_block_device: BlockDevice,
) -> None:
    """Test that configure_coiot_protocol calls http_request with expected params."""
    mock_block_device.http_request = AsyncMock()

    test_address = "10.10.10.10"
    test_port = 5683

    await mock_block_device.configure_coiot_protocol(test_address, test_port)

    mock_block_device.http_request.assert_awaited_once_with(
        "post",
        "settings/advanced",
        {
            "coiot_enable": "true",
            "coiot_peer": f"{test_address}:{test_port}",
        },
    )


@pytest.mark.asyncio
async def test_configure_coiot_protocol_propagates_exceptions(
    mock_block_device: BlockDevice,
) -> None:
    """Test that exceptions from http_request bubble up (no silent swallow)."""
    mock_block_device.http_request = AsyncMock(side_effect=RuntimeError("HTTP failure"))

    with pytest.raises(RuntimeError):
        await mock_block_device.configure_coiot_protocol("10.10.10.10", 5683)


@pytest.mark.asyncio
async def test_create_from_ip(client_session: ClientSession) -> None:
    """Test device creation from ip address triggers a CoAP status request."""
    coap_context = MagicMock(spec=COAP)
    coap_context.request = AsyncMock()

    device = await BlockDevice.create(client_session, coap_context, "10.10.10.10")

    assert device.ip_address == "10.10.10.10"
    coap_context.request.assert_awaited_once_with("10.10.10.10", "s")
    coap_context.subscribe_updates.assert_called_once_with(
        "10.10.10.10", device._coap_message_received
    )


@pytest.mark.asyncio
async def test_create_coap_request_os_error(
    client_session: ClientSession, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device creation ignores OSError from CoAP wakeup request."""
    caplog.set_level("DEBUG")
    coap_context = MagicMock(spec=COAP)
    coap_context.request = AsyncMock(side_effect=OSError("network down"))

    device = await BlockDevice.create(client_session, coap_context, "10.10.10.10")

    assert device.ip_address == "10.10.10.10"
    assert "network down" in caplog.text


@pytest.mark.asyncio
async def test_create_requires_ip_address(client_session: ClientSession) -> None:
    """Test device creation requires ip_address."""
    coap_context = MagicMock(spec=COAP)
    options = ConnectionOptions(ble_device=MagicMock(spec=BLEDevice))

    with pytest.raises(ValueError, match="Block devices require ip_address"):
        await BlockDevice.create(client_session, coap_context, options)


def test_subscribe_with_device_mac() -> None:
    """Test CoAP subscription uses last 6 chars of MAC."""
    device = _create_device(ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF"))

    device.coap_context.subscribe_updates.assert_called_once_with(
        "DDEEFF", device._coap_message_received
    )


@pytest.mark.asyncio
async def test_initialize_new_firmware() -> None:
    """Test initialize fetches cit/d via HTTP and cit/s via CoAP."""
    device = _create_device()
    listener = Mock()
    device.subscribe_updates(listener)
    _mock_http(device, {"settings": SETTINGS, "status": STATUS, "cit/d": COAP_D})
    _mock_coap_replies(device, {"s": COAP_S})

    with patch(GET_INFO, AsyncMock(return_value=SHELLY_INFO)):
        await device.initialize()

    assert device.initialized
    assert device.settings == SETTINGS
    assert device.status == STATUS
    assert device.coap_d == COAP_D
    assert device.coap_s == COAP_S_VALUES
    assert [block.type for block in device.blocks] == ["relay", "device"]
    device.coap_context.request.assert_awaited_once_with("10.10.10.10", "s")
    listener.assert_called_once_with(device, BlockUpdateType.INITIALIZED)


@pytest.mark.asyncio
async def test_initialize_old_firmware() -> None:
    """Test initialize fetches cit/d via CoAP for old firmware."""
    device = _create_device()
    _mock_http(device, {"settings": SETTINGS, "status": STATUS})
    _mock_coap_replies(device, {"d": COAP_D, "s": COAP_S})

    with patch(GET_INFO, AsyncMock(return_value={**SHELLY_INFO, "fw": OLD_FIRMWARE})):
        await device.initialize()

    assert device.initialized
    assert device.coap_d == COAP_D
    assert device.coap_s == COAP_S_VALUES
    assert device.coap_context.request.await_count == 2


@pytest.mark.asyncio
async def test_initialize_skips_cit_s_if_available() -> None:
    """Test initialize skips cit/s request if CoAP status already received."""
    device = _create_device()
    device._update_s(COAP_S, CoapType.PERIODIC)
    _mock_http(device, {"settings": SETTINGS, "status": STATUS, "cit/d": COAP_D})

    with patch(GET_INFO, AsyncMock(return_value=SHELLY_INFO)):
        await device.initialize()

    assert device.initialized
    device.coap_context.request.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_again_refreshes_coap_status() -> None:
    """Test initializing again clears and fetches new CoAP status."""
    device = _create_device()
    device.initialized = True
    device.coap_s = {112: 0}
    _mock_http(device, {"settings": SETTINGS, "status": STATUS, "cit/d": COAP_D})
    _mock_coap_replies(device, {"s": COAP_S})

    with patch(GET_INFO, AsyncMock(return_value=SHELLY_INFO)):
        await device.initialize()

    assert device.coap_s == COAP_S_VALUES


@pytest.mark.asyncio
async def test_initialize_unsupported_firmware_skips_coap() -> None:
    """Test initialize skips CoAP for unsupported firmware."""
    device = _create_device()
    _mock_http(device, {"settings": SETTINGS, "status": STATUS})

    with patch(GET_INFO, AsyncMock(return_value={**SHELLY_INFO, "type": "SHSEN-1"})):
        await device.initialize()

    assert device.initialized
    assert not device.firmware_supported
    assert device.coap_d is None
    device.coap_context.request.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_already_initializing() -> None:
    """Test initialize raises if already initializing."""
    device = _create_device()
    device._initializing = True

    with pytest.raises(RuntimeError, match="Already initializing"):
        await device.initialize()


@pytest.mark.asyncio
async def test_initialize_custom_port() -> None:
    """Test initialize raises for custom port."""
    device = _create_device(ConnectionOptions("10.10.10.10", port=8080))

    with pytest.raises(CustomPortNotSupported):
        await device.initialize()


@pytest.mark.asyncio
async def test_initialize_auth_missing() -> None:
    """Test initialize raises if auth is required but not provided."""
    device = _create_device()

    with (
        patch(GET_INFO, AsyncMock(return_value={**SHELLY_INFO, "auth": True})),
        pytest.raises(InvalidAuthError, match="auth missing and required"),
    ):
        await device.initialize()

    assert not device.initialized
    assert not device._initializing


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (ClientResponseError(Mock(), (), status=401), InvalidAuthError),
        (ClientResponseError(Mock(), (), status=500), DeviceConnectionError),
        (TimeoutError, DeviceConnectionTimeoutError),
        (ClientError, DeviceConnectionError),
        (OSError, DeviceConnectionError),
    ],
)
@pytest.mark.asyncio
async def test_initialize_errors(
    side_effect: Exception, expected: type[Exception]
) -> None:
    """Test initialize error handling."""
    device = _create_device()

    with (
        patch(GET_INFO, AsyncMock(side_effect=side_effect)),
        pytest.raises(expected),
    ):
        await device.initialize()

    assert isinstance(device.last_error, expected)
    assert not device.initialized
    assert not device._initializing


@pytest.mark.asyncio
async def test_initialize_mac_address_mismatch() -> None:
    """Test initialize with MAC address mismatch."""
    device = _create_device()
    error = MacAddressMismatchError("mismatch")

    with (
        patch(GET_INFO, AsyncMock(side_effect=error)),
        pytest.raises(MacAddressMismatchError),
    ):
        await device.initialize()

    assert device.last_error is error


@pytest.mark.asyncio
async def test_shutdown() -> None:
    """Test shutdown unsubscribes once and clears listener."""
    device = _create_device()
    unsub = device._unsub_coap
    device.subscribe_updates(Mock())

    await device.shutdown()
    await device.shutdown()

    unsub.assert_called_once()
    assert device._update_listener is None
    assert device._unsub_coap is None


def test_coap_message_received_online() -> None:
    """Test CoAP message for uninitialized device triggers online update."""
    device = _create_device()
    listener = Mock()
    device.subscribe_updates(listener)

    device._coap_message_received(Mock(payload=None))

    listener.assert_called_once_with(device, BlockUpdateType.ONLINE)
    assert device.coap_s is None


def test_coap_message_received_unknown_payload() -> None:
    """Test CoAP message with unknown payload is ignored."""
    device = _create_device()
    event = asyncio.Event()
    device._coap_response_events["s"] = event

    device._coap_message_received(Mock(payload={"unknown": 1}))

    assert not event.is_set()
    assert device.coap_s is None
    assert device.coap_d is None


def test_coap_message_received_sets_event() -> None:
    """Test CoAP message sets pending response event."""
    device = _create_device()
    event = asyncio.Event()
    device._coap_response_events["d"] = event

    device._coap_message_received(Mock(payload=COAP_D))

    assert event.is_set()
    assert "d" not in device._coap_response_events
    assert device.coap_d == COAP_D


@pytest.mark.parametrize(
    ("coap_type", "update_type"),
    [
        (CoapType.PERIODIC, BlockUpdateType.COAP_PERIODIC),
        (CoapType.REPLY, BlockUpdateType.COAP_REPLY),
    ],
)
def test_update_s_listener(coap_type: CoapType, update_type: BlockUpdateType) -> None:
    """Test CoAP status update notifies listener for initialized device."""
    device = _initialized_device()
    listener = Mock()
    device.subscribe_updates(listener)

    device._coap_message_received(Mock(payload=COAP_S, coap_type=coap_type))

    listener.assert_called_once_with(device, update_type)


@pytest.mark.asyncio
async def test_update() -> None:
    """Test device update via CoAP."""
    device = _create_device()
    _mock_coap_replies(device, {"s": COAP_S})

    await device.update()

    assert device.coap_s == COAP_S_VALUES


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (TimeoutError, DeviceConnectionTimeoutError),
        (OSError, DeviceConnectionError),
    ],
)
@pytest.mark.asyncio
async def test_update_errors(side_effect: Exception, expected: type[Exception]) -> None:
    """Test device update error handling."""
    device = _create_device()
    device.coap_context.request = AsyncMock(side_effect=side_effect)

    with pytest.raises(expected):
        await device.update()

    assert isinstance(device.last_error, expected)


@pytest.mark.asyncio
async def test_update_cit_retry() -> None:
    """Test CoAP cit request is retried on timeout."""
    device = _create_device()
    _mock_coap_replies(device, {"s": COAP_S})
    reply = device.coap_context.request.side_effect

    async def _request(ip: str, path: str) -> None:
        if device.coap_context.request.await_count == 1:
            raise TimeoutError
        await reply(ip, path)

    device.coap_context.request.side_effect = _request

    await device._update_cit_s()

    assert device.coap_context.request.await_count == 2
    assert device.coap_s == COAP_S_VALUES


@pytest.mark.asyncio
async def test_update_cit_retries_exhausted() -> None:
    """Test CoAP cit request raises after all retries time out."""
    device = _create_device()
    device.coap_context.request = AsyncMock(side_effect=TimeoutError)

    with pytest.raises(TimeoutError):
        await device._update_cit_s()

    assert device.coap_context.request.await_count == 3


@pytest.mark.asyncio
async def test_update_shelly() -> None:
    """Test update of /shelly info."""
    device = _create_device()

    with patch(GET_INFO, AsyncMock(return_value=SHELLY_INFO)) as mock_get_info:
        await device.update_shelly()

    mock_get_info.assert_awaited_once_with(device.aiohttp_session, "10.10.10.10")
    assert device.shelly == SHELLY_INFO


@pytest.mark.asyncio
async def test_http_request_with_auth() -> None:
    """Test HTTP request sends authorization header."""
    options = ConnectionOptions("10.10.10.10", auth_header="Basic YWRtaW46cGFzcw==")
    device = _create_device(options)
    device._shelly = {**SHELLY_INFO, "auth": True}
    request = _mock_http(device, {"status": STATUS})

    assert await device.http_request("get", "status") == STATUS
    assert request.call_args.kwargs["headers"] == {"Authorization": options.auth_header}


@pytest.mark.asyncio
async def test_http_request_auth_missing() -> None:
    """Test HTTP request raises if auth is required but not provided."""
    device = _create_device()
    device._shelly = {**SHELLY_INFO, "auth": True}

    with pytest.raises(InvalidAuthError, match="auth missing and required"):
        await device.http_request("get", "status")


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, InvalidAuthError), (500, DeviceConnectionError)],
)
@pytest.mark.asyncio
async def test_http_request_response_error(
    status: int, expected: type[Exception]
) -> None:
    """Test HTTP request response error handling."""
    device = _create_device()
    device._shelly = SHELLY_INFO
    device.aiohttp_session.request = AsyncMock(
        side_effect=ClientResponseError(Mock(), (), status=status)
    )

    with pytest.raises(expected):
        await device.http_request("get", "status")

    assert isinstance(device.last_error, expected)
    device.aiohttp_session.request.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (TimeoutError, DeviceConnectionTimeoutError),
        (ClientError, DeviceConnectionError),
    ],
)
@pytest.mark.asyncio
async def test_http_request_retry_success(
    side_effect: Exception, expected: type[Exception]
) -> None:
    """Test HTTP request is retried once on error."""
    device = _create_device()
    device._shelly = SHELLY_INFO
    resp = Mock()
    resp.json = AsyncMock(return_value=STATUS)
    device.aiohttp_session.request = AsyncMock(side_effect=[side_effect, resp])

    assert await device.http_request("get", "status") == STATUS
    assert isinstance(device.last_error, expected)
    assert device.aiohttp_session.request.await_count == 2


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (TimeoutError, DeviceConnectionTimeoutError),
        (ClientError, DeviceConnectionError),
    ],
)
@pytest.mark.asyncio
async def test_http_request_retry_failure(
    side_effect: Exception, expected: type[Exception]
) -> None:
    """Test HTTP request raises if retry also fails."""
    device = _create_device()
    device._shelly = SHELLY_INFO
    device.aiohttp_session.request = AsyncMock(side_effect=side_effect)

    with pytest.raises(expected):
        await device.http_request("get", "status")

    assert device.aiohttp_session.request.await_count == 2


@pytest.mark.parametrize(
    ("method", "args", "expected_args"),
    [
        ("switch_light_mode", ("color",), ("get", "settings", {"mode": "color"})),
        ("trigger_ota_update", (), ("get", "ota", {"update": "true"})),
        ("trigger_ota_update", (True,), ("get", "ota", {"beta": "true"})),
        (
            "trigger_ota_update",
            (False, "http://fw.bin"),
            ("get", "ota", {"url": "http://fw.bin"}),
        ),
        ("trigger_reboot", (), ("get", "reboot")),
        ("trigger_shelly_gas_self_test", (), ("get", "self_test")),
        ("trigger_shelly_gas_mute", (), ("get", "mute")),
        ("trigger_shelly_gas_unmute", (), ("get", "unmute")),
        (
            "set_shelly_motion_detection",
            (True,),
            ("get", "settings", {"motion_enable": "true"}),
        ),
        (
            "set_shelly_motion_detection",
            (False,),
            ("get", "settings", {"motion_enable": "false"}),
        ),
    ],
)
@pytest.mark.asyncio
async def test_device_actions(
    mock_block_device: BlockDevice,
    method: str,
    args: tuple[Any, ...],
    expected_args: tuple[Any, ...],
) -> None:
    """Test device action methods call http_request with expected params."""
    mock_block_device.http_request = AsyncMock()

    await getattr(mock_block_device, method)(*args)

    mock_block_device.http_request.assert_awaited_once()
    call_args = mock_block_device.http_request.call_args
    assert (*call_args.args, *call_args.kwargs.values()) == expected_args


@pytest.mark.asyncio
async def test_set_thermostat_state(mock_block_device: BlockDevice) -> None:
    """Test set_thermostat_state calls http_request with expected params."""
    mock_block_device.http_request = AsyncMock()

    await mock_block_device.set_thermostat_state(1, target_t=21)

    mock_block_device.http_request.assert_awaited_once_with(
        "get", "thermostat/1", {"target_t": 21}
    )


def test_device_properties() -> None:
    """Test device properties."""
    device = _initialized_device()

    assert device.gen == 1
    assert device.model == "SHSW-1"
    assert device.firmware_version == NEW_FIRMWARE
    assert device.firmware_supported
    assert device.hostname == "shelly1-AABBCC"
    assert device.name == "Living Room"
    assert device.last_error is None
    assert not device.requires_auth


def test_device_name_fallback_to_hostname() -> None:
    """Test device name falls back to hostname."""
    device = _initialized_device(settings={**SETTINGS, "name": None})

    assert device.name == "shelly1-AABBCC"


def test_device_properties_not_initialized() -> None:
    """Test device properties raise if not initialized."""
    device = _create_device()

    with pytest.raises(NotInitialized):
        _ = device.settings
    with pytest.raises(NotInitialized):
        _ = device.status
    with pytest.raises(NotInitialized):
        _ = device.shelly


def test_device_properties_missing_data() -> None:
    """Test settings and status raise auth error if data is missing."""
    device = _create_device()
    device.initialized = True

    with pytest.raises(InvalidAuthError):
        _ = device.settings
    with pytest.raises(InvalidAuthError):
        _ = device.status


def test_requires_auth_wrong_gen() -> None:
    """Test requires_auth raises for wrong device generation."""
    device = _create_device()
    device._shelly = {"type": "SHSW-1", "fw": NEW_FIRMWARE}

    with pytest.raises(WrongShellyGen):
        _ = device.requires_auth


def test_block_properties() -> None:
    """Test block properties and values."""
    device = _initialized_device()
    relay, dev = device.blocks

    assert relay.index == 0
    assert relay.description == "relay_0"
    assert relay.channel == "0"
    assert dev.channel is None
    assert relay.sensor_ids == {"output": 112, "mode": 9101}
    assert dev.sensor_ids == {"mode": 9101, "deviceTemp": 3104}
    assert relay.info("output") == COAP_D["sen"][0]
    assert relay.current_values() == {"output": 1, "mode": "relay"}
    assert relay.output == 1
    assert dev.deviceTemp == 40.5
    assert str(relay) == "<relay {'I': 0, 'D': 'relay_0'}>"


def test_block_without_coap_status() -> None:
    """Test block values without CoAP status."""
    device = _initialized_device()
    device.coap_s = None
    relay = device.blocks[0]

    assert relay.current_values() == {}
    assert relay.output is None


def test_block_missing_attribute() -> None:
    """Test block raises AttributeError for unknown attribute."""
    device = _initialized_device()

    with pytest.raises(
        AttributeError,
        match=(
            f"Device SHSW-1 with firmware {NEW_FIRMWARE} has no attribute "
            "'power' in block relay"
        ),
    ):
        _ = device.blocks[0].power


@pytest.mark.parametrize(
    ("temperature_unit", "expected_id"), [("C", 3104), ("F", 3105)]
)
def test_block_duplicate_temperature_sensor(
    temperature_unit: str, expected_id: int
) -> None:
    """Test duplicate temperature sensor uses configured unit."""
    device = _create_device(
        ConnectionOptions("10.10.10.10", temperature_unit=temperature_unit)
    )
    sensors = {
        3104: {"I": 3104, "T": "T", "D": "deviceTemp", "U": "C", "L": 0},
        3105: {"I": 3105, "T": "T", "D": "deviceTemp", "U": "F", "L": 0},
    }

    block = Block.create(device, {"I": 0, "D": "device"}, sensors)

    assert block.sensor_ids == {"deviceTemp": expected_id}


def test_block_duplicate_non_temperature_sensor() -> None:
    """Test duplicate non-temperature sensor raises."""
    device = _create_device()
    sensors = {
        112: {"I": 112, "T": "S", "D": "output", "L": 0},
        113: {"I": 113, "T": "S", "D": "output", "L": 0},
    }

    with pytest.raises(
        ValueError, match="Found duplicate description for non-temperature sensor"
    ):
        Block.create(device, {"I": 0, "D": "relay_0"}, sensors)


@pytest.mark.parametrize(("output", "turn"), [(1, "off"), (0, "on")])
@pytest.mark.asyncio
async def test_block_toggle(output: int, turn: str) -> None:
    """Test block toggle sets opposite state."""
    device = _initialized_device()
    device.coap_s[112] = output
    device.http_request = AsyncMock(return_value={"ison": not output})

    assert await device.blocks[0].toggle() == {"ison": not output}

    device.http_request.assert_awaited_once_with("get", "relay/0", {"turn": turn})


@pytest.mark.parametrize(
    ("settings", "path"),
    [
        ({"device": {"type": MODEL_RGBW2}, "mode": "color"}, "color/0"),
        ({"device": {"type": "SHBLB-1"}, "mode": "white"}, "light/0"),
    ],
)
@pytest.mark.asyncio
async def test_light_block_set_state(settings: dict[str, Any], path: str) -> None:
    """Test light block set_state path."""
    device = _initialized_device(settings=settings)
    device.http_request = AsyncMock(return_value={})
    block = Block.create(device, {"I": 0, "D": "light_0"}, {})

    assert isinstance(block, LightBlock)
    await block.set_state(turn="on")

    device.http_request.assert_awaited_once_with("get", path, {"turn": "on"})
