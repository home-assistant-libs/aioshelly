"""Tests for block_device.coap module."""

import asyncio
import logging
import runpy
import socket
import struct
import warnings
from ipaddress import IPv4Address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from aioshelly.block_device import coap as coap_module
from aioshelly.block_device.coap import (
    COAP,
    COAP_OPTION_DEVICE_ID,
    CoapMessage,
    CoapType,
    InvalidMessage,
    discovery_dump,
    socket_init,
)

ADDR = ("192.168.1.10", 5683)
DEVICE_ID_VALUE = b"SHSW-1#AABBCCDDEEFF#2"
PAYLOAD = b'{"G": [[0, 112, 1]]}'


def _option(delta: int, value: bytes) -> bytes:
    """Encode a single COAP option (delta and length extended as needed)."""

    def _nibble(num: int) -> tuple[int, bytes]:
        if num < 13:
            return num, b""
        if num < 269:
            return 13, bytes([num - 13])
        return 14, (num - 269).to_bytes(2, "big")

    delta_nibble, delta_ext = _nibble(delta)
    length_nibble, length_ext = _nibble(len(value))
    return bytes([(delta_nibble << 4) | length_nibble]) + delta_ext + length_ext + value


def _message(
    code: int = 30,
    options: bytes = b"",
    payload: bytes = PAYLOAD,
) -> bytes:
    """Build a raw COAP message."""
    return struct.pack("!BBH", 0x50, code, 1) + options + b"\xff" + payload


def _device_message(device_id: bytes = DEVICE_ID_VALUE, code: int = 30) -> bytes:
    """Build a raw COAP message with a device id option."""
    return _message(code, _option(COAP_OPTION_DEVICE_ID, device_id))


def test_coap_message_periodic() -> None:
    """Test parsing a periodic message with a device id option."""
    msg = CoapMessage(ADDR, _device_message())

    assert msg.ip == ADDR[0]
    assert msg.port == ADDR[1]
    assert msg.code == 30
    assert msg.mid == 1
    assert msg.coap_type is CoapType.PERIODIC
    assert msg.options == {COAP_OPTION_DEVICE_ID: DEVICE_ID_VALUE}
    assert msg.payload == {"G": [[0, 112, 1]]}


def test_coap_message_reply() -> None:
    """Test parsing a reply message without options."""
    msg = CoapMessage(ADDR, _message(code=69))

    assert msg.coap_type is CoapType.REPLY
    assert msg.options == {}


def test_coap_message_multiple_options() -> None:
    """Test parsing options with small and 1-byte extended delta/length."""
    long_value = b"x" * 20
    options = _option(1, b"a") + _option(20, long_value)
    msg = CoapMessage(ADDR, _message(options=options))

    assert msg.options == {1: b"a", 21: long_value}


def test_coap_message_too_short() -> None:
    """Test message shorter than the header."""
    with pytest.raises(InvalidMessage, match="Message too short"):
        CoapMessage(ADDR, b"\x50\x1e")


def test_coap_message_wrong_code() -> None:
    """Test message with unsupported code."""
    with pytest.raises(InvalidMessage, match="Wrong type, 1"):
        CoapMessage(ADDR, _message(code=1))


def test_coap_message_no_data() -> None:
    """Test message without payload marker."""
    with pytest.raises(InvalidMessage, match="without data"):
        CoapMessage(ADDR, struct.pack("!BBH", 0x50, 30, 1))


def test_coap_message_empty_data() -> None:
    """Test message with payload marker but empty payload."""
    with pytest.raises(InvalidMessage, match="without data"):
        CoapMessage(ADDR, _message(payload=b""))


def test_coap_message_option_absent() -> None:
    """Test option announced with a length larger than remaining data."""
    raw = struct.pack("!BBH", 0x50, 30, 1) + b"\x15ab"
    with pytest.raises(InvalidMessage, match="Option announced but absent"):
        CoapMessage(ADDR, raw)


@pytest.mark.parametrize(
    "option_bytes",
    [
        b"\xd0",  # delta 13 without extended byte
        b"\xe0\x01",  # delta 14 with only one extended byte
    ],
)
def test_coap_message_option_ended_prematurely(option_bytes: bytes) -> None:
    """Test extended option values missing their extension bytes."""
    raw = struct.pack("!BBH", 0x50, 30, 1) + option_bytes
    with pytest.raises(InvalidMessage, match="Option ended prematurely"):
        CoapMessage(ADDR, raw)


def test_coap_message_option_partial_payload_marker() -> None:
    """Test option delta of 15 (reserved for payload marker)."""
    raw = struct.pack("!BBH", 0x50, 30, 1) + b"\xf1a"
    with pytest.raises(InvalidMessage, match="partial payload marker"):
        CoapMessage(ADDR, raw)


@pytest.mark.parametrize("payload", [b"not json", b"\xff\xfe"])
def test_coap_message_invalid_payload(payload: bytes) -> None:
    """Test payload that is not valid JSON or not valid UTF-8."""
    with pytest.raises(InvalidMessage, match="not a valid JSON format"):
        CoapMessage(ADDR, _message(payload=payload))


@pytest.fixture
def mock_socket() -> Any:
    """Patch socket.socket used by socket_init."""
    with patch.object(coap_module.socket, "socket") as mock_sock_cls:
        yield mock_sock_cls.return_value


def test_socket_init_default_interface(mock_socket: Mock) -> None:
    """Test socket init joining multicast on the default interface."""
    sock = socket_init(1234)

    assert sock is mock_socket
    mock_socket.bind.assert_called_once_with(("", 1234))
    mock_socket.setblocking.assert_called_once_with(False)
    mreq = struct.pack("=4sl", socket.inet_aton("224.0.1.187"), socket.INADDR_ANY)
    mock_socket.setsockopt.assert_called_with(
        socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
    )


def test_socket_init_specific_interfaces(
    mock_socket: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test socket init with one failing and one successful interface."""
    ips = [IPv4Address("10.0.0.1"), IPv4Address("10.0.0.2")]
    calls = 0

    def _setsockopt(level: int, *_: Any) -> None:
        nonlocal calls
        if level != socket.IPPROTO_IP:
            return
        calls += 1
        if calls == 1:
            raise OSError("fail")

    mock_socket.setsockopt.side_effect = _setsockopt

    with caplog.at_level(logging.WARNING):
        assert socket_init(5683, ips) is mock_socket

    assert "Failed to join multicast group on 10.0.0.1" in caplog.text
    mock_socket.setsockopt.assert_called_with(
        socket.IPPROTO_IP,
        socket.IP_ADD_MEMBERSHIP,
        socket.inet_aton("224.0.1.187") + ips[1].packed,
    )


def test_socket_init_all_interfaces_fail(mock_socket: Mock) -> None:
    """Test socket init raises when no interface joins the multicast group."""
    error = OSError("fail")

    def _setsockopt(level: int, *_: Any) -> None:
        if level == socket.IPPROTO_IP:
            raise error

    mock_socket.setsockopt.side_effect = _setsockopt

    with pytest.raises(OSError, match="fail") as exc_info:
        socket_init(5683, [IPv4Address("10.0.0.1")])

    assert exc_info.value is error


@pytest.mark.asyncio
async def test_coap_initialize() -> None:
    """Test COAP initialize creates a datagram endpoint."""
    coap = COAP()
    sock = MagicMock()
    loop = asyncio.get_running_loop()
    ips = [IPv4Address("10.0.0.1")]

    with (
        patch.object(coap_module, "socket_init", return_value=sock) as mock_init,
        patch.object(loop, "create_datagram_endpoint", AsyncMock()) as mock_endpoint,
    ):
        await coap.initialize(1234, ips)

    mock_init.assert_called_once_with(1234, ips)
    assert coap.sock is sock
    mock_endpoint.assert_awaited_once()
    factory = mock_endpoint.call_args.args[0]
    assert factory() is coap
    assert mock_endpoint.call_args.kwargs == {"sock": sock}


@pytest.mark.asyncio
async def test_coap_request() -> None:
    """Test COAP request sends the expected message."""
    coap = COAP()
    transport = Mock()
    coap.connection_made(transport)

    await coap.request("192.168.1.10", "s")

    transport.sendto.assert_called_once_with(
        b"\x50\x01\x00\x0a\xb3cit\x01s\xff\x00", ("192.168.1.10", 5683)
    )


def test_coap_close() -> None:
    """Test COAP close with and without a transport."""
    coap = COAP()
    coap.close()  # no transport, no error

    transport = Mock()
    coap.connection_made(transport)
    assert coap.transport is transport

    coap.close()
    transport.close.assert_called_once()


def test_datagram_received_invalid_message(caplog: pytest.LogCaptureFixture) -> None:
    """Test invalid datagrams are ignored."""
    callback = Mock()
    coap = COAP(callback)

    with caplog.at_level(logging.DEBUG):
        coap.datagram_received(b"\x00", ADDR)

    callback.assert_not_called()
    assert "Invalid Message from host 192.168.1.10" in caplog.text


def test_datagram_received_missing_device_id(caplog: pytest.LogCaptureFixture) -> None:
    """Test message without device id calls global callback only."""
    callback = Mock()
    subscriber = Mock()
    coap = COAP(callback)
    coap.subscribe_updates(ADDR[0], subscriber)

    with caplog.at_level(logging.DEBUG):
        coap.datagram_received(_message(), ADDR)

    callback.assert_called_once()
    assert isinstance(callback.call_args.args[0], CoapMessage)
    subscriber.assert_not_called()
    assert "missing device id option" in caplog.text


@pytest.mark.parametrize("device_id", [b"no-separator", b"\xff#\xfe#"])
def test_datagram_received_invalid_device_id(
    device_id: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Test message with malformed device id is not dispatched."""
    subscriber = Mock()
    coap = COAP()
    coap.subscribe_updates(ADDR[0], subscriber)

    with caplog.at_level(logging.DEBUG):
        coap.datagram_received(_device_message(device_id), ADDR)

    subscriber.assert_not_called()
    assert "Invalid device id from host" in caplog.text


def test_datagram_received_subscribed_device_id() -> None:
    """Test message dispatched by device id subscription first."""
    by_id = Mock()
    by_ip = Mock()
    coap = COAP()
    coap.subscribe_updates("DDEEFF", by_id)
    coap.subscribe_updates(ADDR[0], by_ip)

    coap.datagram_received(_device_message(), ADDR)

    by_id.assert_called_once()
    assert by_id.call_args.args[0].ip == ADDR[0]
    by_ip.assert_not_called()


def test_datagram_received_subscribed_ip() -> None:
    """Test message dispatched by IP subscription."""
    by_ip = Mock()
    coap = COAP()
    coap.subscribe_updates(ADDR[0], by_ip)

    coap.datagram_received(_device_message(), ADDR)

    by_ip.assert_called_once()


def test_datagram_received_no_subscription() -> None:
    """Test message without matching subscription."""
    other = Mock()
    coap = COAP()
    coap.subscribe_updates("10.0.0.99", other)

    coap.datagram_received(_device_message(), ADDR)

    other.assert_not_called()


def test_subscribe_updates_unsubscribe() -> None:
    """Test subscribe returns a callable that removes the subscription."""
    callback = Mock()
    coap = COAP()

    unsub = coap.subscribe_updates("DDEEFF", callback)
    assert coap.subscriptions == {"DDEEFF": callback}

    assert unsub() is callback
    assert coap.subscriptions == {}


@pytest.mark.asyncio
async def test_coap_context_manager() -> None:
    """Test COAP async context manager initializes and closes."""
    with (
        patch.object(COAP, "initialize", AsyncMock()) as mock_init,
        patch.object(COAP, "close") as mock_close,
    ):
        async with COAP() as coap:
            assert isinstance(coap, COAP)
            mock_init.assert_awaited_once_with()
            mock_close.assert_not_called()

    mock_close.assert_called_once_with()


@pytest.mark.asyncio
async def test_discovery_dump(capsys: pytest.CaptureFixture[str]) -> None:
    """Test discovery dump prints received messages."""

    async def _initialize(self: COAP, *_: Any) -> None:
        self.datagram_received(_message(), ADDR)

    with (
        patch.object(COAP, "initialize", autospec=True, side_effect=_initialize),
        patch.object(
            coap_module.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError)
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await discovery_dump()

    assert capsys.readouterr().out == "192.168.1.10 {'G': [[0, 112, 1]]}\n"


def test_main_keyboard_interrupt() -> None:
    """Test running the module as a script handles KeyboardInterrupt."""

    def _run(coro: Any) -> None:
        coro.close()
        raise KeyboardInterrupt

    with (
        patch("asyncio.run", side_effect=_run) as mock_run,
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module("aioshelly.block_device.coap", run_name="__main__")

    mock_run.assert_called_once()
