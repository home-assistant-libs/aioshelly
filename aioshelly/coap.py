"""COAP for Shelly."""
import asyncio
import json
import socket
import struct

# Socket buffer
BUFFER = 2048


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

    def __init__(self):
        self.sock = socket_init()

    async def request(self, ip: str, path: str):
        """Device CoAP request."""
        loop = asyncio.get_running_loop()
        msg = (
            b"\x50\x01\x00\x0A\xb3cit\x01" + path.encode() + b"\xFF"
        )
        self.sock.sendto(msg, (ip, 5683))
        response = await loop.sock_recv(self.sock, BUFFER)
        if path == "d":
            header = b'"blk":'
            prefix = '{"blk":'
        else:
            header = b'"G":'
            prefix = '{"G":'
        payload_bytes = response.split(header)[1]
        payload = prefix + payload_bytes.decode()
        return json.loads(payload)

    def close(self):
        self.sock.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, type, value, traceback):
        self.close()
