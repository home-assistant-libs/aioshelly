"""COAP for Shelly."""
import asyncio
import json
import socket
import struct

# Socket buffer
BUFFER = 2048


class CoapMessage:
    def __init__(self, sender_addr, payload: bytes):
        self.ip = sender_addr[0]
        self.port = sender_addr[1]
        header, payload = payload.split(b"\xff", 1)
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


class COAP:
    """Initialize the COAP manager."""

    def __init__(self, status_update_received=None):
        self.sock = None
        self.status_update_received = status_update_received

    async def initialize(self):
        loop = asyncio.get_running_loop()
        self.sock = socket_init()
        if self.status_update_received:
            await loop.create_datagram_endpoint(lambda: DiscoveryProtocol(self.status_update_received), sock=self.sock)

    async def request(self, ip: str, path: str):
        """Device CoAP request."""
        loop = asyncio.get_running_loop()
        msg = (
            b"\x50\x01\x00\x0A\xb3cit\x01" + path.encode() + b"\xFF"
        )
        self.sock.sendto(msg, (ip, 5683))
        response = await loop.sock_recv(self.sock, BUFFER)

        return CoapMessage((ip, 5683), response).payload

    def close(self):
        self.sock.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, type, value, traceback):
        self.close()


async def discovery_dump():
    async with COAP(lambda msg: print(msg.ip, msg.payload)):
        while True:
            await asyncio.sleep(.1)


if __name__ == '__main__':
    try:
        asyncio.run(discovery_dump())
    except KeyboardInterrupt:
        pass
