"""COAP for Shelly."""
import asyncio
import json
import logging
import socket
import struct


_LOGGER = logging.getLogger(__name__)


class CoapMessage:
    """Represents a received coap message."""

    def __init__(self, sender_addr, payload: bytes):
        """Initialize a coap message."""
        self.ip = sender_addr[0]
        self.port = sender_addr[1]

        try:
            (vttkl, code, mid) = struct.unpack("!BBH", payload[:4])
        except struct.error:
            raise error.UnparsableMessage("Incoming message too short for CoAP")
        if (code != 30 and code !=69):
            _LOGGER.warning("Received packet type: %s, host ip: %s", code, self.ip)
            self.payload = None
        else:
            parts = payload.rsplit(b"\xff", 1)
            self.header = parts[0]
            self.payload = json.loads(parts[1].decode()) if len(parts) > 1 else {}


class CoapMessage:
    def __init__(self, sender_addr, payload: bytes):
        self.ip = sender_addr[0]
        self.port = sender_addr[1]
        header, payload = payload.rsplit(b"\xff", 1)
        self.header = header
        self.payload = json.loads(payload.decode())


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, msg_received) -> None:
        self.msg_received = msg_received

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.msg_received(CoapMessage(addr, data))


def socket_init():
    """Init UDP socket to send/receive data with Shelly devices."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 5683))
    mreq = struct.pack("=4sl", socket.inet_aton("224.0.1.187"), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setblocking(False)
    return sock


class COAP(asyncio.DatagramProtocol):
    """COAP manager."""

    def __init__(self, message_received=None):
        """Initialize COAP manager."""
        self.sock = None
        # Will receive all updates
        self._message_received = message_received
        self.subscriptions = {}

    async def initialize(self):
        """Initialize the COAP manager."""
        loop = asyncio.get_running_loop()
        self.sock = socket_init()
        await loop.create_datagram_endpoint(lambda: self, sock=self.sock)

    async def request(self, ip: str, path: str):
        """Request a CoAP message.

        Subscribe with `subscribe_updates` to receive answer.
        """
        msg = b"\x50\x01\x00\x0A\xb3cit\x01" + path.encode() + b"\xFF"
        self.sock.sendto(msg, (ip, 5683))

    def close(self):
        """Close."""
        self.sock.close()

    def datagram_received(self, data, addr):
        """Handle incoming datagram messages."""
        msg = CoapMessage(addr, data)

        if self._message_received:
            self._message_received(msg)

        if msg.ip in self.subscriptions:
            self.subscriptions[msg.ip](msg)

    def subscribe_updates(self, ip, message_received):
        """Subscribe to received updates."""
        self.subscriptions[ip] = message_received
        return lambda: self.subscriptions.pop(ip)

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, _type, _value, _traceback):
        self.close()


async def discovery_dump():
    """Dump all discovery data as it comes in."""
    async with COAP(lambda msg: print(msg.ip, msg.payload)):
        while True:
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(discovery_dump())
    except KeyboardInterrupt:
        pass
