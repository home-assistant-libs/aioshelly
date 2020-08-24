import json

import aiohttp
import aiocoap


MODEL_NAMES = {
    "SHSW-1": "Shelly 1",
    "SHSW-PM": "Shelly 1PM",
    "SHSW-25": "Shelly 2.5",
}


class ShellyError(Exception):
    """Base class for aioshelly errors."""


class AuthRequired(ShellyError):
    """Raised during initialization if auth is required but not given."""


async def get_info(aiohttp_session: aiohttp.ClientSession, ip):
    async with aiohttp_session.get(
        f"http://{ip}/shelly", raise_for_status=True
    ) as resp:
        return await resp.json()


class Device:
    def __init__(
        self,
        coap_context: aiocoap.Context,
        aiohttp_session: aiohttp.ClientSession,
        ip: str,
    ):
        self.coap_context = coap_context
        self.aiohttp_session = aiohttp_session
        self.ip = ip
        self.d = None
        self.blocks = None
        self.s = None
        self.settings = None
        self.shelly = None

    @classmethod
    async def create(cls, ip, aiohttp_session):
        coap_context = await aiocoap.Context.create_client_context()
        instance = cls(coap_context, aiohttp_session, ip)

        try:
            await instance.initialize()
        except Exception:
            await coap_context.shutdown()
            raise

        return instance

    async def initialize(self):
        self.shelly = await get_info(self.aiohttp_session, self.ip)

        if self.shelly["auth"]:
            raise AuthRequired

        self.d = await self.coap_request("d")
        blocks = []

        for blk in self.d["blk"]:
            blk_index = blk["I"]
            blk_sensors = {
                val["I"]: val
                for val in self.d["sen"]
                if (
                    val["L"] == blk_index
                    if isinstance(val["L"], int)
                    else blk_index in val["L"]
                )
            }
            block = Block.create(self, blk, blk_sensors)

            if block:
                blocks.append(block)

        self.blocks = blocks

        await self.update()

        self.settings = await self.http_request("get", "settings")

    async def update(self):
        self.s = {info[1]: info[2] for info in (await self.coap_request("s"))["G"]}

    async def coap_request(self, path):
        request = aiocoap.Message(code=aiocoap.GET, uri=f"coap://{self.ip}/cit/{path}")
        response = await self.coap_context.request(request).response
        return json.loads(response.payload)

    async def http_request(self, method, path, params=None):
        resp = await self.aiohttp_session.request(
            method, f"http://{self.ip}/{path}", params=params
        )
        return await resp.json()

    async def shutdown(self):
        await self.coap_context.shutdown()


class Block:
    TYPES = {}
    type = None

    def __init_subclass__(cls, blk_type, **kwargs):
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)  # type: ignore
        Block.TYPES[blk_type] = cls

    @staticmethod
    def create(device, blk, sensors):
        blk_type = blk["D"].split("_")[0]
        cls = Block.TYPES.get(blk_type, Block)
        return cls(device, blk_type, blk, sensors)

    def __init__(self, device, blk_type, blk, sensors):
        self.type = blk_type
        self.device = device
        # https://shelly-api-docs.shelly.cloud/#coiot-device-description-cit-d
        # blk
        # {
        #     "I": id,
        #     "D": description
        # }
        self.blk = blk
        # Sensors:
        # {
        #     "I": id,
        #     "T": type,
        #     "D": description,
        #     "U": unit,
        #     "R": range,
        #     "L": links
        # }
        self.sensors = sensors
        self.sensor_ids = {val["D"]: val["I"] for val in sensors.values()}

    @property
    def index(self):
        return self.blk["I"]

    @property
    def description(self):
        return self.blk["D"]

    def current_values(self):
        return {
            desc: self.device.s.get(index) for desc, index in self.sensor_ids.items()
        }

    def __str__(self):
        return f"<{self.type} {self.blk}>"


class RelayBlock(Block, blk_type="relay"):
    @property
    def channel(self):
        return self.description.split("_")[1]

    @property
    def power(self):
        return self.device.s[self.sensor_ids["power"]]

    @property
    def output(self):
        return self.device.s[self.sensor_ids["output"]]

    @property
    def input(self):
        return self.device.s[self.sensor_ids["input"]]

    async def turn_on(self):
        return await self.device.http_request(
            "get", f"relay/{self.channel}", {"turn": "on"}
        )

    async def turn_off(self):
        return await self.device.http_request(
            "get", f"relay/{self.channel}", {"turn": "off"}
        )

    async def toggle(self):
        if self.output:
            return await self.turn_off()
        else:
            return await self.turn_on()
