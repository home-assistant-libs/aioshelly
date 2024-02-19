# Run with python3 example.py -h for help
"""aioshelly usage example."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from functools import partial
from pathlib import Path
from types import FrameType
from typing import Any

import aiohttp
import orjson

from aioshelly.block_device import COAP, BlockDevice
from aioshelly.common import ConnectionOptions
from aioshelly.const import BLOCK_GENERATIONS, MODEL_NAMES, WS_API_URL
from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
    MacAddressMismatchError,
    WrongShellyGen,
)
from aioshelly.rpc_device import RpcDevice, WsServer
from tools.common import close_connections, create_device, device_updated

coap_context = COAP()
ws_context = WsServer()


async def connect_and_save(
    options: ConnectionOptions, init: bool, gen: int | None
) -> None:
    """Save fixture single device."""
    async with aiohttp.ClientSession() as aiohttp_session:
        try:
            device = await create_device(aiohttp_session, options, init, gen)
        except FirmwareUnsupported as err:
            print(f"Device firmware not supported, error: {repr(err)}")
            return
        except InvalidAuthError as err:
            print(f"Invalid or missing authorization, error: {repr(err)}")
            return
        except DeviceConnectionError as err:
            print(f"Error connecting to {options.ip_address}, error: {repr(err)}")
            return
        except MacAddressMismatchError as err:
            print(f"MAC address mismatch, error: {repr(err)}")
            return
        except WrongShellyGen:
            print(f"Wrong Shelly generation {gen}, device gen: {2 if gen==1 else 1}")
            return

        save_endpoints(device)

        device.subscribe_updates(partial(device_updated, action=save_endpoints))

        while True:
            await asyncio.sleep(0.1)


def save_endpoints(device: BlockDevice | RpcDevice) -> None:
    """Save device endpoints."""
    data_raw = {"shelly": device.shelly.copy(), "status": device.status.copy()}

    if device.gen in BLOCK_GENERATIONS:
        data_raw.update({"settings": device.settings.copy()})
        data_normalized = _redact_block_data(data_raw)
    else:
        data_raw.update({"config": device.config.copy()})
        data_normalized = _redact_rpc_data(data_raw)

    gen = device.gen
    model = device.model
    name = MODEL_NAMES.get(model, "Unknown")
    version = device.firmware_version.replace("/", "-")
    fixture_path = Path("../fixtures") / f"gen{gen}_{name}_{model}_{version}.json"

    print(f"Saving fixture to {fixture_path}")

    with open(fixture_path, "wb") as file:
        file.write(
            orjson.dumps(  # pylint: disable=no-member
                data_normalized,
                option=orjson.OPT_INDENT_2  # pylint: disable=no-member
                | orjson.OPT_SORT_KEYS,  # pylint: disable=no-member
            )
        )
        file.write(b"\n")

    close_connections()


NORMALIZE_VALUES = {
    "wifi": "Wifi-Network-Name",
    "wifi_mac": "11:22:33:44:55:66",
    "device_mac": "AABBCCDDEEFF",
    "device_short_mac": "DDEEFF",
    "device_name": "Test Name",
    "switch_name": "Switch Test Name",
    "input_name": "Input Test Name",
    "script_name": "Script Test Name",
    "em_name": "Energy Monitor Test Name",
    "mqtt_server": "mqtt.test.server",
    "sntp_server": "sntp.test.server",
    "coiot_peer": "home-assistant.server:8123",
}


def _redact_block_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact data for BLOCK devices."""
    status: dict[str, Any] = data["status"]
    shelly: dict[str, Any] = data["shelly"]
    settings: dict[str, Any] = data["settings"]

    real_mac: str = status["mac"]
    short_mac: str = status["mac"][6:12]

    # Shelly endpoint
    shelly["name"] = NORMALIZE_VALUES["device_name"]
    shelly["mac"] = NORMALIZE_VALUES["device_mac"]

    # Status endpoint
    status["mac"] = NORMALIZE_VALUES["device_mac"]

    if status["wifi_sta"].get("ssid"):
        status["wifi_sta"]["ssid"] = NORMALIZE_VALUES["wifi"]

    # Config endpoint

    if settings["coiot"].get("peer"):
        settings["coiot"]["peer"] = NORMALIZE_VALUES["coiot_peer"]

    # Some devices use short MAC (uppercase/lowercase)
    settings["device"]["hostname"] = settings["device"]["hostname"].replace(
        real_mac, NORMALIZE_VALUES["device_mac"]
    )
    settings["device"]["hostname"] = settings["device"]["hostname"].replace(
        short_mac, NORMALIZE_VALUES["device_short_mac"]
    )
    settings["device"]["mac"] = NORMALIZE_VALUES["device_mac"]

    # Some devices use MAC and short MAC (uppercase/lowercase)
    settings["mqtt"]["id"] = settings["mqtt"]["id"].replace(
        real_mac, NORMALIZE_VALUES["device_mac"]
    )
    settings["mqtt"]["id"] = settings["mqtt"]["id"].replace(
        real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower()
    )
    settings["mqtt"]["id"] = settings["mqtt"]["id"].replace(
        short_mac, NORMALIZE_VALUES["device_short_mac"]
    )
    settings["mqtt"]["id"] = settings["mqtt"]["id"].replace(
        short_mac.lower(), NORMALIZE_VALUES["device_short_mac"].lower()
    )

    settings["name"] = NORMALIZE_VALUES["device_name"]
    # Some devices use MAC and short MAC (uppercase/lowercase)
    settings["wifi_ap"]["ssid"] = settings["wifi_ap"]["ssid"].replace(
        real_mac, NORMALIZE_VALUES["device_mac"]
    )
    settings["wifi_ap"]["ssid"] = settings["wifi_ap"]["ssid"].replace(
        short_mac, NORMALIZE_VALUES["device_short_mac"]
    )
    settings["wifi_sta"]["ssid"] = NORMALIZE_VALUES["wifi"]

    # Updata dataset
    data.update({"settings": settings})
    data.update({"shelly": shelly})
    data.update({"status": status})

    return data


def _redact_rpc_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact data for RPC devices."""
    config: dict[str, Any] = data["config"]
    status: dict[str, Any] = data["status"]
    shelly: dict[str, Any] = data["shelly"]

    real_mac: str = status["sys"]["mac"]
    device = config["sys"]["device"]

    # Config endpoint
    device["name"] = NORMALIZE_VALUES["device_name"]
    device["mac"] = NORMALIZE_VALUES["device_mac"]

    # Some devices use MAC uppercase, others lowercase
    config["mqtt"]["client_id"] = config["mqtt"]["client_id"].replace(
        real_mac, NORMALIZE_VALUES["device_mac"]
    )
    config["mqtt"]["client_id"] = config["mqtt"]["client_id"].replace(
        real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower()
    )
    config["mqtt"]["server"] = NORMALIZE_VALUES["mqtt_server"]

    if config["mqtt"].get("topic_prefix"):
        # Some devices use MAC uppercase, others lowercase
        config["mqtt"]["topic_prefix"] = config["mqtt"]["topic_prefix"].replace(
            real_mac, NORMALIZE_VALUES["device_mac"]
        )
        config["mqtt"]["topic_prefix"] = config["mqtt"]["topic_prefix"].replace(
            real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower()
        )

    if config["sys"].get("sntp"):
        config["sys"]["sntp"]["server"] = NORMALIZE_VALUES["sntp_server"]

    config_prefixes = ("switch:", "input:", "em:", "script:")
    for key in config:
        if key.startswith(config_prefixes):
            key_name, id_ = key.split(":")
            config[key]["name"] = f"{key_name} {id_}"

    for id_ in range(5):
        if config.get(f"thermostat:{id_}"):
            config[f"thermostat:{id_}"]["sensor"] = config[f"thermostat:{id_}"][
                "sensor"
            ].replace(real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower())
            config[f"thermostat:{id_}"]["actuator"] = config[f"thermostat:{id_}"][
                "actuator"
            ].replace(real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower())

    if config.get("wifi"):
        config["wifi"] = NORMALIZE_VALUES["wifi"]

    # Shelly endpoint
    shelly["name"] = NORMALIZE_VALUES["device_name"]
    # Some devices use MAC uppercase, others lowercase
    shelly["id"] = shelly["id"].replace(real_mac, NORMALIZE_VALUES["device_mac"])
    shelly["id"] = shelly["id"].replace(
        real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower()
    )
    shelly["mac"] = NORMALIZE_VALUES["device_mac"]

    if shelly.get("auth_domain"):
        shelly["auth_domain"] = shelly["auth_domain"].replace(
            real_mac, NORMALIZE_VALUES["device_mac"]
        )
        shelly["auth_domain"] = shelly["auth_domain"].replace(
            real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower()
        )

    # Status endpoint
    status["sys"]["mac"] = NORMALIZE_VALUES["device_mac"]

    if status["wifi"].get("ssid"):
        status["wifi"]["ssid"] = NORMALIZE_VALUES["wifi"]

    if status["wifi"].get("mac"):
        status["wifi"]["mac"] = NORMALIZE_VALUES["wifi_mac"]

    if status["sys"].get("id"):
        # Some devices use MAC uppercase, others lowercase
        status["sys"]["id"] = status["sys"]["id"].replace(
            real_mac, NORMALIZE_VALUES["device_mac"]
        )
        status["sys"]["id"] = status["sys"]["id"].replace(
            real_mac.lower(), NORMALIZE_VALUES["device_mac"].lower()
        )

    # Updata dataset
    data.update({"config": config})
    data.update({"shelly": shelly})
    data.update({"status": status})

    return data


def get_arguments() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="aioshelly example")
    parser.add_argument(
        "--ip_address", "-ip", type=str, help="Test single device by IP address"
    )
    parser.add_argument(
        "--coap_port",
        "-cp",
        type=int,
        default=5683,
        help="Specify CoAP UDP port (default=5683)",
    )
    parser.add_argument(
        "--ws_port",
        "-wp",
        type=int,
        default=8123,
        help="Specify WebSocket TCP port (default=8123)",
    )
    parser.add_argument(
        "--ws_api_url",
        "-au",
        type=str,
        default=WS_API_URL,
        help=f"Specify WebSocket API URL (default={WS_API_URL})",
    )
    parser.add_argument(
        "--init", "-i", action="store_true", help="Init device(s) at startup"
    )
    parser.add_argument("--username", "-u", type=str, help="Set device username")
    parser.add_argument("--password", "-p", type=str, help="Set device password")

    parser.add_argument(
        "--gen1", "-g1", action="store_true", help="Force Gen1 (CoAP) device"
    )
    parser.add_argument(
        "--gen2", "-g2", action="store_true", help="Force Gen 2 (RPC) device"
    )
    parser.add_argument(
        "--gen3", "-g3", action="store_true", help="Force Gen 3 (RPC) device"
    )
    parser.add_argument(
        "--debug", "-deb", action="store_true", help="Enable debug level for logging"
    )
    parser.add_argument(
        "--mac", "-m", type=str, help="Optional device MAC to subscribe for updates"
    )

    arguments = parser.parse_args()

    return parser, arguments


async def main() -> None:
    """Run main."""
    parser, args = get_arguments()

    await coap_context.initialize(args.coap_port)
    await ws_context.initialize(args.ws_port, args.ws_api_url)

    if not args.init and not (args.gen1 or args.gen2 or args.gen3):
        parser.error("specify gen if no device init at startup")
    if args.gen1 and args.gen2:
        parser.error("--gen1 and --gen2 can't be used together")
    elif args.gen1 and args.gen3:
        parser.error("--gen1 and --gen3 can't be used together")
    elif args.gen2 and args.gen3:
        parser.error("--gen2 and --gen3 can't be used together")

    gen = None
    if args.gen1:
        gen = 1
    elif args.gen2:
        gen = 2
    elif args.gen3:
        gen = 3

    if args.debug:
        logging.basicConfig(level="DEBUG", force=True)

    def handle_sigint(_exit_code: int, _frame: FrameType) -> None:
        """Handle Keyboard signal interrupt (ctrl-c)."""
        coap_context.close()
        ws_context.close()
        sys.exit()

    signal.signal(signal.SIGINT, handle_sigint)

    if args.ip_address:
        if args.username and args.password is None:
            parser.error("--username and --password must be used together")
        options = ConnectionOptions(
            args.ip_address, args.username, args.password, device_mac=args.mac
        )
        await connect_and_save(options, args.init, gen)
    else:
        parser.error("--ip_address or --devices must be specified")


if __name__ == "__main__":
    asyncio.run(main())
