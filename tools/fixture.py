# Run with python3 fixture.py -h for help
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

import orjson
from aiohttp import ClientSession
from common import (
    close_connections,
    coap_context,
    create_device,
    device_updated,
    init_device,
    ws_context,
)

from aioshelly.block_device import BlockDevice
from aioshelly.common import ConnectionOptions
from aioshelly.const import BLOCK_GENERATIONS, DEVICES, WS_API_URL
from aioshelly.rpc_device import RpcDevice


async def connect_and_save(
    options: ConnectionOptions, init: bool, gen: int | None
) -> None:
    """Save fixture single device."""
    async with ClientSession() as aiohttp_session:
        device = await create_device(aiohttp_session, options, gen)

        if init:
            if not await init_device(device):
                return

            save_endpoints(device)

        device.subscribe_updates(partial(device_updated, action=save_endpoints))

        # This is for diagnostic purposes only.
        while True:  # noqa: ASYNC110
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
    if shelly_device := DEVICES.get(model):
        name = shelly_device.name
    else:
        name = f"Unknown ({model})"
    version = device.firmware_version.replace("/", "-")
    current_path = Path(__file__)
    fixture_path = (
        current_path.parent.parent.joinpath("fixtures")
        / f"gen{gen}_{name}_{model}_{version}.json"
    )

    print(f"Saving fixture to {fixture_path}")

    with Path.open(fixture_path, "wb") as file:
        file.write(
            orjson.dumps(
                data_normalized,
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
            )
        )
        file.write(b"\n")

    close_connections()


REDACTED_VALUES = {
    "wifi": "Wifi-Network-Name",
    "wifi_mac": "11:22:33:44:55:66",
    "device_mac": "AABBCCDDEEFF",
    "device_mac_lower": "aabbccddeeff",
    "device_short_mac": "DDEEFF",
    "device_short_mac_lower": "ddeeff",
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
    settings: dict[str, dict[str, dict[str, Any] | str]] = data["settings"]

    real_mac: str = status["mac"]
    short_mac: str = status["mac"][6:12]

    # Shelly endpoint
    shelly["name"] = REDACTED_VALUES["device_name"]
    shelly["mac"] = REDACTED_VALUES["device_mac"]

    # Status endpoint
    status["mac"] = REDACTED_VALUES["device_mac"]

    if "ssid" in status["wifi_sta"]:
        status["wifi_sta"]["ssid"] = REDACTED_VALUES["wifi"]

    # Config endpoint

    if "peer" in settings["coiot"]:
        settings["coiot"]["peer"] = REDACTED_VALUES["coiot_peer"]

    # Some devices use short MAC (uppercase/lowercase)
    device = settings["device"]
    device["hostname"] = (
        device["hostname"]
        .replace(real_mac, REDACTED_VALUES["device_mac"])
        .replace(short_mac, REDACTED_VALUES["device_short_mac"])
    )
    device["mac"] = REDACTED_VALUES["device_mac"]

    # Some devices use MAC and short MAC (uppercase/lowercase)
    mqtt = settings["mqtt"]
    mqtt["id"] = (
        mqtt["id"]
        .replace(real_mac, REDACTED_VALUES["device_mac"])
        .replace(real_mac.lower(), REDACTED_VALUES["device_mac_lower"])
        .replace(short_mac, REDACTED_VALUES["device_short_mac"])
        .replace(short_mac.lower(), REDACTED_VALUES["device_short_mac"].lower())
    )

    settings["name"] = REDACTED_VALUES["device_name"]
    # Some devices use MAC and short MAC (uppercase/lowercase)
    settings["wifi_ap"]["ssid"] = (
        settings["wifi_ap"]["ssid"]
        .replace(real_mac, REDACTED_VALUES["device_mac"])
        .replace(short_mac, REDACTED_VALUES["device_short_mac"])
    )
    settings["wifi_sta"]["ssid"] = REDACTED_VALUES["wifi"]

    return data


def _redact_rpc_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact data for RPC devices."""
    config: dict[str, dict[str, Any] | str] = data["config"]
    status: dict[str, dict[str, dict[str, Any] | str] | str] = data["status"]
    shelly: dict[str, dict[str, Any] | str] = data["shelly"]

    real_mac: str = status["sys"]["mac"]
    device = config["sys"]["device"]

    # Config endpoint
    device["name"] = REDACTED_VALUES["device_name"]
    device["mac"] = REDACTED_VALUES["device_mac"]

    # Some devices use MAC uppercase, others lowercase
    mqtt = config["mqtt"]
    mqtt["client_id"] = (
        mqtt["client_id"]
        .replace(real_mac, REDACTED_VALUES["device_mac"])
        .replace(real_mac.lower(), REDACTED_VALUES["device_mac_lower"])
    )
    mqtt["server"] = REDACTED_VALUES["mqtt_server"]

    if mqtt.get("topic_prefix"):
        # Some devices use MAC uppercase, others lowercase
        mqtt["topic_prefix"] = (
            mqtt["topic_prefix"]
            .replace(real_mac, REDACTED_VALUES["device_mac"])
            .replace(real_mac.lower(), REDACTED_VALUES["device_mac_lower"])
        )

    if sntp := config["sys"].get("sntp"):
        sntp["server"] = REDACTED_VALUES["sntp_server"]

    config_prefixes = ("switch:", "input:", "em:", "script:")
    for key, value in config.items():
        if key.startswith(config_prefixes):
            key_name, id_ = key.split(":")
            value["name"] = f"{key_name} {id_}"

    for id_ in range(5):
        if thermostat := config.get(f"thermostat:{id_}"):
            thermostat["sensor"] = thermostat["sensor"].replace(
                real_mac.lower(), REDACTED_VALUES["device_mac_lower"]
            )
            thermostat["actuator"] = thermostat["actuator"].replace(
                real_mac.lower(), REDACTED_VALUES["device_mac_lower"]
            )

    if "wifi" in config:
        config["wifi"] = REDACTED_VALUES["wifi"]

    # Shelly endpoint
    shelly["name"] = REDACTED_VALUES["device_name"]
    # Some devices use MAC uppercase, others lowercase
    shelly["id"] = (
        shelly["id"]
        .replace(real_mac, REDACTED_VALUES["device_mac"])
        .replace(real_mac.lower(), REDACTED_VALUES["device_mac_lower"])
    )
    shelly["mac"] = REDACTED_VALUES["device_mac"]

    if auth_domain := shelly.get("auth_domain"):
        shelly["auth_domain"] = auth_domain.replace(
            real_mac, REDACTED_VALUES["device_mac"]
        ).replace(real_mac.lower(), REDACTED_VALUES["device_mac_lower"])

    # Status endpoint
    status["sys"]["mac"] = REDACTED_VALUES["device_mac"]

    if status["wifi"].get("ssid"):
        status["wifi"]["ssid"] = REDACTED_VALUES["wifi"]

    if status["wifi"].get("mac"):
        status["wifi"]["mac"] = REDACTED_VALUES["wifi_mac"]

    if id_ := status["sys"].get("id"):
        # Some devices use MAC uppercase, others lowercase
        status["sys"]["id"] = id_.replace(
            real_mac, REDACTED_VALUES["device_mac"]
        ).replace(real_mac.lower(), REDACTED_VALUES["device_mac_lower"])

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
        "--gen4", "-g4", action="store_true", help="Force Gen 4 (RPC) device"
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

    if not args.init and not (args.gen1 or args.gen2 or args.gen3 or args.gen4):
        parser.error("specify gen if no device init at startup")

    gen_list = (args.gen1, args.gen2, args.gen3, args.gen4)
    if len([gen for gen in gen_list if gen]) > 1:
        parser.error(
            "You can only use one of --gen1, --gen2, --gen3 or --gen4 at a time"
        )

    gen = None
    if args.gen1:
        gen = 1
    elif args.gen2:
        gen = 2
    elif args.gen3:
        gen = 3
    elif args.gen4:
        gen = 4

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
