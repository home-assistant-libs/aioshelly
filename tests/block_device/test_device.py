"""Tests for block_device.device module."""

import asyncio
import socket
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock

import pytest
from aiohttp import ClientError
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientResponseError
from bleak.backends.device import BLEDevice
from yarl import URL

from aioshelly.block_device.device import COAP, Block, BlockDevice, LightBlock
from aioshelly.common import ConnectionOptions
from aioshelly.exceptions import (
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    InvalidAuthError,
)


# Reusable fixture for aiohttp_session mock with mock_response and async .json()
@pytest.fixture
def mock_aiohttp_session() -> Mock:
    """Fixture that returns a mocked aiohttp session."""
    aiohttp_session = Mock()
    mock_response = MagicMock()

    async def fake_json(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True}

    mock_response.json = fake_json
    aiohttp_session.request = AsyncMock(return_value=mock_response)
    return aiohttp_session


class DummyBlock(Block):
    """Dummy block for testing Block.toggle."""

    def __init__(
        self,
        device: BlockDevice,
        blk_type: str = "relay",
        blk: dict | None = None,
        sensors: dict | None = None,
    ) -> None:
        """Initialize DummyBlock for toggle tests."""
        if blk is None:
            blk = {"I": "0", "D": "relay_0"}
        if sensors is None:
            sensors = {"sensor": {"D": "sensor", "I": "0", "T": "T", "U": "U"}}
        super().__init__(device, blk_type, blk, sensors)
        self.output = False


def build_dummy_device(
    aiohttp_session: Any | None = None,
) -> BlockDevice:
    """Build a BlockDevice with mocked dependencies for testing."""
    coap_context = Mock()
    if aiohttp_session is None:
        aiohttp_session = AsyncMock()
    options = ConnectionOptions(ip_address="1.2.3.4", device_mac="AABBCCDDEEFF")
    device = BlockDevice(
        coap_context=coap_context,
        aiohttp_session=aiohttp_session,
        options=options,
    )
    device._settings = {"device": {"type": "SHSW-1"}, "mode": "white"}
    device._shelly = {"auth": False, "fw": "fake", "type": "SHSW-1"}
    device.initialized = True
    return device


@pytest.mark.asyncio
async def test_blockdevice_set_state_basic(mock_aiohttp_session: Mock) -> None:
    """Test BlockDevice.set_state with typical path/channel."""
    dev = build_dummy_device(mock_aiohttp_session)
    result = await dev.set_state("relay", "0", foo="bar")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_blockdevice_set_state_none_path(mock_aiohttp_session: Mock) -> None:
    """Test BlockDevice.set_state with None path and channel."""
    dev = build_dummy_device(mock_aiohttp_session)
    result = await dev.set_state(None, None, foo=1)
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_block_toggle_calls_set_state(mock_aiohttp_session: Mock) -> None:
    """Test Block.toggle calls device.set_state with correct args."""
    dummy_device = build_dummy_device(mock_aiohttp_session)
    block = DummyBlock(dummy_device)
    block.output = True
    await block.toggle()
    mock_aiohttp_session.request.assert_called()
    block.output = False
    await block.toggle()
    mock_aiohttp_session.request.assert_called()


@pytest.mark.asyncio
async def test_lightblock_set_state_calls_device(mock_aiohttp_session: Mock) -> None:
    """Test LightBlock.set_state calls device.set_state with correct parameters."""
    dummy_device = build_dummy_device(mock_aiohttp_session)
    # RGBW2 device
    dummy_device.settings["device"]["type"] = "SHRGBW2"
    dummy_device.settings["mode"] = "color"
    block = LightBlock(dummy_device, "light", {"I": "0", "D": "light_0"}, {})
    await block.set_state(brightness=100)
    mock_aiohttp_session.request.assert_called()
    # Non-RGBW2 device
    dummy_device.settings["device"]["type"] = "SHSW-1"
    block = LightBlock(dummy_device, "light", {"I": "0", "D": "light_0"}, {})
    await block.set_state(brightness=50)
    mock_aiohttp_session.request.assert_called()


def _build_block_device(client_session: ClientSession) -> BlockDevice:
    """Create a BlockDevice ready for direct _http_request testing."""
    coap_context = COAP()
    options = ConnectionOptions("10.10.10.10", device_mac="AABBCCDDEEFF")
    block_device = BlockDevice(coap_context, client_session, options)
    block_device._shelly = {
        "auth": False,
        "fw": "20240213-140411/1.2.0-gb1b9aa8",
        "type": "SHSW-1",
    }
    return block_device


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
    mock_block_device._http_request = AsyncMock()

    test_address = "10.10.10.10"
    test_port = 5683

    await mock_block_device.configure_coiot_protocol(test_address, test_port)

    mock_block_device._http_request.assert_awaited_once_with(
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
    mock_block_device._http_request = AsyncMock(
        side_effect=RuntimeError("HTTP failure")
    )

    with pytest.raises(RuntimeError):
        await mock_block_device.configure_coiot_protocol("10.10.10.10", 5683)


@pytest.mark.asyncio
async def test_http_request_success(client_session: ClientSession) -> None:
    """Test _http_request returns JSON payload on success."""
    block_device = _build_block_device(client_session)
    response = AsyncMock()
    response.json = AsyncMock(return_value={"ok": True})
    client_session.request = AsyncMock(return_value=response)

    result = await block_device._http_request("get", "status", {"x": "1"})

    assert result == {"ok": True}
    client_session.request.assert_awaited_once_with(
        "get",
        URL.build(scheme="http", host="10.10.10.10", path="/status"),
        params={"x": "1"},
        auth=None,
        raise_for_status=True,
        timeout=ANY,
    )


@pytest.mark.asyncio
async def test_http_request_auth_missing_guard(client_session: ClientSession) -> None:
    """Test _http_request fails early if auth is required but missing."""
    block_device = _build_block_device(client_session)
    block_device._shelly = {
        "auth": True,
        "fw": "20240213-140411/1.2.0-gb1b9aa8",
        "type": "SHSW-1",
    }
    client_session.request = AsyncMock()

    with pytest.raises(InvalidAuthError, match="auth missing and required"):
        await block_device._http_request("get", "status")

    client_session.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_request_unauthorized_maps_to_invalid_auth(
    client_session: ClientSession,
) -> None:
    """Test _http_request maps HTTP 401 to InvalidAuthError."""
    block_device = _build_block_device(client_session)
    request_info = Mock(real_url=URL("http://10.10.10.10/status"))
    client_session.request = AsyncMock(
        side_effect=ClientResponseError(request_info, (), status=401)
    )

    with pytest.raises(InvalidAuthError):
        await block_device._http_request("get", "status")

    assert isinstance(block_device.last_error, InvalidAuthError)


@pytest.mark.asyncio
async def test_http_request_timeout_retries_once(client_session: ClientSession) -> None:
    """Test _http_request retries once after timeout and then succeeds."""
    block_device = _build_block_device(client_session)
    response = AsyncMock()
    response.json = AsyncMock(return_value={"ok": True})
    client_session.request = AsyncMock(side_effect=[TimeoutError(), response])

    result = await block_device._http_request("get", "status")

    assert result == {"ok": True}
    assert client_session.request.await_count == 2


@pytest.mark.asyncio
async def test_http_request_timeout_retry_exhausted(
    client_session: ClientSession,
) -> None:
    """Test _http_request raises DeviceConnectionTimeoutError after retry."""
    block_device = _build_block_device(client_session)
    client_session.request = AsyncMock(side_effect=[TimeoutError(), TimeoutError()])

    with pytest.raises(DeviceConnectionTimeoutError):
        await block_device._http_request("get", "status")

    assert client_session.request.await_count == 2
    assert isinstance(block_device.last_error, DeviceConnectionTimeoutError)


@pytest.mark.asyncio
async def test_http_request_connect_error_retries_once(
    client_session: ClientSession,
) -> None:
    """Test _http_request retries once after connect error and succeeds."""
    block_device = _build_block_device(client_session)
    response = AsyncMock()
    response.json = AsyncMock(return_value={"ok": True})
    client_session.request = AsyncMock(side_effect=[OSError("boom"), response])

    result = await block_device._http_request("get", "status")

    assert result == {"ok": True}
    assert client_session.request.await_count == 2


@pytest.mark.asyncio
async def test_http_request_connect_error_retry_exhausted(
    client_session: ClientSession,
) -> None:
    """Test _http_request raises DeviceConnectionError after retry."""
    block_device = _build_block_device(client_session)
    client_session.request = AsyncMock(side_effect=[ClientError(), ClientError()])

    with pytest.raises(DeviceConnectionError):
        await block_device._http_request("get", "status")

    assert client_session.request.await_count == 2
    assert isinstance(block_device.last_error, DeviceConnectionError)
