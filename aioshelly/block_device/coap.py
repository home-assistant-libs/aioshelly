"""COAP for Shelly."""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
from collections.abc import Callable
from enum import Enum, auto
from ipaddress import IPv4Address
from types import TracebackType
from typing import TYPE_CHECKING, Self, cast

from ..const import DEFAULT_COAP_PORT, END_OF_OPTIONS_MARKER, PERIODIC_COAP_TYPE_CODE
from ..json import JSONDecodeError, json_loads

COAP_OPTION_DEVICE_ID = 3332

_LOGGER = logging.getLogger(__name__)


class CoapError(Exception):
    """Base class for COAP errors."""


class InvalidMessage(CoapError):
    """Raised during COAP message parsing errors."""


class CoapType(Enum):
    """Coap message type."""

    PERIODIC = auto()
    REPLY = auto()


class CoapMessage:
    """Represents a received coap message."""

    def __init__(self, sender_addr: tuple[str, int], payload: bytes) -> None:
        """Initialize a coap message."""
        self.ip = sender_addr[0]
        self.port = sender_addr[1]
        self.options: dict[int, bytes] = {}
        self.coap_type = CoapType.REPLY

        try:
            self.vttkl, self.code, self.mid = struct.unpack("!BBH", payload[:4])
        except struct.error as err:
            raise InvalidMessage("Message too short") from err

        if self.code not in (30, 69):
            raise InvalidMessage(f"Wrong type, {self.code}")

        raw_data = payload[4:]
        option_number = 0
        data = b""

        # parse options
        while raw_data:
            if raw_data[0] == END_OF_OPTIONS_MARKER:
                data = raw_data[1:]
                break

            delta = (raw_data[0] & 0xF0) >> 4
            length = raw_data[0] & 0x0F
            (delta, raw_data) = self._read_extended_field_value(delta, raw_data[1:])
            (length, raw_data) = self._read_extended_field_value(length, raw_data)
            option_number += delta

            if len(raw_data) < length:
                raise InvalidMessage("Option announced but absent")

            self.options[option_number] = raw_data[:length]
            raw_data = raw_data[length:]

        if not data:
            raise InvalidMessage("Received message without data")

        try:
            self.payload = json_loads(data.decode())
        except (JSONDecodeError, UnicodeDecodeError) as err:
            raise InvalidMessage(
                f"Message type {self.code} is not a valid JSON format: {payload!s}"
            ) from err

        if self.code == PERIODIC_COAP_TYPE_CODE:
            self.coap_type = CoapType.PERIODIC

        _LOGGER.debug(
            "CoapMessage: ip=%s, type=%s(%s), options=%s, payload=%s",
            self.ip,
            self.coap_type,
            self.code,
            self.options,
            self.payload,
        )

    @staticmethod
    def _read_extended_field_value(value: int, raw_data: bytes) -> tuple[int, bytes]:
        """Decode large values of option delta and option length."""
        if 0 <= value < 13:  # noqa: PLR2004
            return (value, raw_data)
        if value == 13:  # noqa: PLR2004
            if len(raw_data) < 1:
                raise InvalidMessage("Option ended prematurely")
            return (raw_data[0] + 13, raw_data[1:])
        if value == 14:  # noqa: PLR2004
            if len(raw_data) < 2:  # noqa: PLR2004
                raise InvalidMessage("Option ended prematurely")
            return (int.from_bytes(raw_data[:2], "big") + 269, raw_data[2:])

        raise InvalidMessage("Option contained partial payload marker.")


def socket_init(
    socket_port: int = DEFAULT_COAP_PORT,
    socket_ips: list[IPv4Address] | None = None,
) -> socket.socket:
    """Init UDP socket to send/receive data with Shelly devices."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", socket_port))
    sock.setblocking(False)
    multicast_ip_bytes = socket.inet_aton("224.0.1.187")

    if not socket_ips:
        _LOGGER.debug("Socket initialized on port %s (default interface)", socket_port)
        # INADDR_ANY indicates that the OS will chose an interface to join the given
        # multicast group.
        mreq = struct.pack("=4sl", multicast_ip_bytes, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    had_successful_joins = False
    last_exception: OSError | None = None
    for address in socket_ips:
        _LOGGER.debug("Socket initialized on %s:%s", address, socket_port)
        mreq = multicast_ip_bytes + address.packed
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            had_successful_joins = True
        except OSError as ex:
            _LOGGER.warning("Failed to join multicast group on %s", address)
            last_exception = ex

    if not had_successful_joins and last_exception is not None:
        raise last_exception

    return sock


class COAP(asyncio.DatagramProtocol):
    """COAP manager."""

    def __init__(self, message_received: Callable | None = None) -> None:
        """Initialize COAP manager."""
        self.sock: socket.socket | None = None
        # Will receive all updates
        self._message_received = message_received
        self.subscriptions: dict[str, Callable] = {}
        self.transport: asyncio.DatagramTransport | None = None

    async def initialize(
        self,
        socket_port: int = DEFAULT_COAP_PORT,
        socket_ips: list[IPv4Address] | None = None,
    ) -> None:
        """Initialize the COAP manager."""
        loop = asyncio.get_running_loop()
        self.sock = socket_init(socket_port, socket_ips)
        await loop.create_datagram_endpoint(lambda: self, sock=self.sock)

    async def request(self, ip: str, path: str) -> None:
        """Request a CoAP message.

        Subscribe with `subscribe_updates` to receive answer.
        """
        if TYPE_CHECKING:
            assert self.transport is not None

        msg = b"\x50\x01\x00\x0a\xb3cit\x01" + path.encode() + b"\xff\x00"
        _LOGGER.debug("Sending request 'cit/%s' to device %s", path, ip)
        self.transport.sendto(msg, (ip, 5683))

    def close(self) -> None:
        """Close."""
        if self.transport is not None:
            self.transport.close()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """When the socket is set up."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming datagram messages."""
        host_ip = addr[0]
        try:
            msg = CoapMessage(addr, data)
        except InvalidMessage as err:
            _LOGGER.debug("Invalid Message from host %s: %s", host_ip, err)
            return

        if self._message_received:
            self._message_received(msg)

        if COAP_OPTION_DEVICE_ID not in msg.options:
            _LOGGER.debug("Message from host %s missing device id option", host_ip)
            return

        try:
            device_id = msg.options[COAP_OPTION_DEVICE_ID].decode().split("#")[1][-6:]
        except (UnicodeDecodeError, IndexError) as err:
            _LOGGER.debug("Invalid device id from host %s: %s", host_ip, err)
            return

        if device_id in self.subscriptions:
            _LOGGER.debug("Calling CoAP message update for device id %s", device_id)
            self.subscriptions[device_id](msg)
            return

        if msg.ip in self.subscriptions:
            _LOGGER.debug("Calling CoAP message update for host %s", msg.ip)
            self.subscriptions[msg.ip](msg)

    def subscribe_updates(
        self, ip_or_device_id: str, message_received: Callable
    ) -> Callable:
        """Subscribe to received updates."""
        _LOGGER.debug("Adding device %s to CoAP message subscriptions", ip_or_device_id)
        self.subscriptions[ip_or_device_id] = message_received
        return lambda: self.subscriptions.pop(ip_or_device_id)

    async def __aenter__(self) -> Self:
        """Entering async context manager."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Leaving async context manager."""
        self.close()


async def discovery_dump() -> None:
    """Dump all discovery data as it comes in."""
    async with COAP(lambda msg: print(msg.ip, msg.payload)):  # noqa: T201
        # This is for diagnostic purposes only.
        while True:  # noqa: ASYNC110
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:  # noqa: SIM105
        asyncio.run(discovery_dump())
    except KeyboardInterrupt:
        pass
