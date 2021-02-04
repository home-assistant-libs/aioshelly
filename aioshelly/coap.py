"""COAP for Shelly."""
import asyncio
import json
import logging
import socket
import struct
from typing import Optional, cast

import netifaces
from netaddr import IPAddress, IPNetwork

_LOGGER = logging.getLogger(__name__)

MAIN_MULTICAST_IP = "224.0.1.187"
WF200_MULTICAST_IP = "224.0.1.188"

CIDR_NET_10 = "10.0.0.0/8"
CIDR_NET_172 = "172.16.0.0/12"
CIDR_NET_192 = "192.168.0.0/16"


class CoapMessage:
    """Represents a received coap message."""

    def __init__(self, sender_addr, payload: bytes):
        """Initialize a coap message."""
        self.ip = sender_addr[0]
        self.port = sender_addr[1]

        try:
            self.vttkl, self.code, self.mid = struct.unpack("!BBH", payload[:4])
        except struct.error as err:
            raise ValueError("Incoming message too short for CoAP") from err

        if self.code in (30, 69):
            try:
                self.payload = json.loads(payload.rsplit(b"\xff", 1)[1].decode())
            except json.decoder.JSONDecodeError:
                _LOGGER.error(
                    "CoAP message of type %s from host %s is not a valid JSON format: %s",
                    self.code,
                    self.ip,
                    payload,
                )
                self.payload = None
        else:
            _LOGGER.debug("Received packet type: %s, host ip: %s", self.code, self.ip)
            self.payload = None


def get_all_ips():
    """Get all ip from ethernet interfaces."""
    ip_list = []
    for iface in netifaces.interfaces():
        iface_details = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in iface_details:
            for net_addr in CIDR_NET_10, CIDR_NET_172, CIDR_NET_192:
                ip_addr = iface_details[netifaces.AF_INET][0]["addr"]
                if IPAddress(ip_addr) in IPNetwork(net_addr):
                    ip_list.append(ip_addr)
    return ip_list


def socket_init():
    """Init UDP socket to send/receive data with Shelly devices."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 5683))

    for ip in get_all_ips():
        for multicast_ip in MAIN_MULTICAST_IP, WF200_MULTICAST_IP:
            _LOGGER.debug("Adding ip %s to multicast %s membership", ip, multicast_ip)
            group = socket.inet_aton(multicast_ip) + socket.inet_aton(ip)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group)

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
        self.transport: Optional[asyncio.DatagramTransport] = None

    async def initialize(self):
        """Initialize the COAP manager."""
        loop = asyncio.get_running_loop()
        self.sock = socket_init()
        await loop.create_datagram_endpoint(lambda: self, sock=self.sock)

    async def request(self, ip: str, path: str):
        """Request a CoAP message.

        Subscribe with `subscribe_updates` to receive answer.
        """
        assert self.transport is not None
        msg = b"\x50\x01\x00\x0A\xb3cit\x01" + path.encode() + b"\xFF"
        self.transport.sendto(msg, (ip, 5683))

    def close(self):
        """Close."""
        self.transport.close()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """When the socket is set up."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data, addr):
        """Handle incoming datagram messages."""
        msg = CoapMessage(addr, data)

        # Don't know how to handle these right now.
        if msg.payload is None:
            return

        if self._message_received:
            self._message_received(msg)

        if msg.ip in self.subscriptions:
            self.subscriptions[msg.ip](msg)

    def subscribe_updates(self, ip, message_received):
        """Subscribe to received updates."""
        self.subscriptions[ip] = message_received
        return lambda: self.subscriptions.pop(ip)

    async def __aenter__(self):
        """Entering async context manager."""
        await self.initialize()
        return self

    async def __aexit__(self, _type, _value, _traceback):
        """Leaving async context manager."""
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
