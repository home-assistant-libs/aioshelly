"""COAP for Shelly."""
import asyncio
import ipaddress
import json
import logging
import socket
import struct
import threading
from typing import Optional, cast

import netifaces
from scapy.contrib.igmp import IGMP
from scapy.layers.inet import IP
from scapy.sendrecv import send, sniff

MAIN_MULTICAST_IP = "224.0.1.187"
WF200_MULTICAST_IP = "224.0.1.188"

MULTICAST_QUERY_IGMPTYPE = 0x11
MULTICAST_QUERY_GRP = "224.0.0.1"
MULTICAST_QUERY_TIMEOUT = 240

_LOGGER = logging.getLogger(__name__)


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


def get_network_objects(objtype: str):
    """Get all ip/iface from system interfaces."""
    obj_list = []
    ifaces = netifaces.interfaces()

    for iface in ifaces:
        iface_details = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in iface_details:
            if objtype == "iface":
                obj_list.append(iface)
            else:
                obj_list.append(iface_details[netifaces.AF_INET][0]["addr"])
    return obj_list


def socket_init():
    """Init UDP socket to send/receive data with Shelly devices."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 5683))

    for ip in get_network_objects("ip"):
        for multicast_ip in MAIN_MULTICAST_IP, WF200_MULTICAST_IP:
            _LOGGER.debug("Adding ip %s to multicast %s membership", ip, multicast_ip)
            group = socket.inet_aton(multicast_ip) + socket.inet_aton(ip)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group)

    sock.setblocking(False)
    return sock


class MulticastQuerier:
    """Multicast querier management."""

    def __init__(self):
        """Initialize multicast querier thread."""
        _LOGGER.debug("Multicast querier thread started")
        self.stop_thread = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        """Start sniffing for multicast query."""
        filter_igmp_query = f"igmp and igmp[0] == {int(MULTICAST_QUERY_IGMPTYPE)} and (igmp[4:4] == {int(ipaddress.IPv4Address(MAIN_MULTICAST_IP))} or igmp[4:4] == 0)"
        pkt_snd = IP(dst=MULTICAST_QUERY_GRP) / IGMP(
            type=MULTICAST_QUERY_IGMPTYPE,
            mrcode=100,
            gaddr=MAIN_MULTICAST_IP,
        )
        while not self.stop_thread:
            result = sniff(
                filter=filter_igmp_query,
                store=1,
                count=1,
                timeout=MULTICAST_QUERY_TIMEOUT,
            )
            _LOGGER.debug("Multicast query sniff result: %s", result)
            if not result:
                _LOGGER.info(
                    "Multicast query not received in %s seconds",
                    MULTICAST_QUERY_TIMEOUT,
                )
                for eth_iface in get_network_objects("iface"):
                    send(pkt_snd, iface=eth_iface, verbose=False)
                    _LOGGER.info("Multicast query sent for %s interface", eth_iface)
            else:
                _LOGGER.info(
                    "Multicast query received from network, no action required"
                )

    def stop(self):
        """Stop multicast querier thread."""
        _LOGGER.debug("Multicast querier thread stopped")
        self.stop_thread = True


class COAP(asyncio.DatagramProtocol):
    """COAP manager."""

    def __init__(self, message_received=None):
        """Initialize COAP manager."""
        self.sock = None
        # Will receive all updates
        self._message_received = message_received
        self.subscriptions = {}
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.querier = None

    async def initialize(self):
        """Initialize the COAP manager."""
        loop = asyncio.get_running_loop()
        self.sock = socket_init()
        await loop.create_datagram_endpoint(lambda: self, sock=self.sock)
        self.querier = MulticastQuerier()

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
        self.querier.stop()

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
