# Run with python3 example.py -h for help
"""aioshelly usage example."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import traceback
from datetime import datetime
from types import FrameType
from typing import Any, cast

import aiohttp

import aioshelly
from aioshelly.block_device import BLOCK_VALUE_UNIT, COAP, BlockDevice, BlockUpdateType
from aioshelly.common import ConnectionOptions
from aioshelly.const import BLOCK_GENERATIONS, MODEL_NAMES, RPC_GENERATIONS, WS_API_URL
from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
    MacAddressMismatchError,
    ShellyError,
    WrongShellyGen,
)
from aioshelly.rpc_device import RpcDevice, RpcUpdateType, WsServer

coap_context = COAP()
ws_context = WsServer()


async def create_device(
    aiohttp_session: aiohttp.ClientSession,
    options: ConnectionOptions,
    init: bool,
    gen: int | None,
) -> Any:
    """Create a Gen1/Gen2/Gen3 device."""
    if gen is None:
        if info := await aioshelly.common.get_info(aiohttp_session, options.ip_address):
            gen = info.get("gen", 1)
        else:
            raise ShellyError("Unknown Gen")

    if gen in BLOCK_GENERATIONS:
        return await BlockDevice.create(aiohttp_session, coap_context, options, init)

    if gen in RPC_GENERATIONS:
        return await RpcDevice.create(aiohttp_session, ws_context, options, init)

    raise ShellyError("Unknown Gen")


async def test_single(
    options: ConnectionOptions, init: bool, gen: int | None, dump: bool
) -> None:
    """Test single device."""
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

        print_device(device, dump)

        device.subscribe_updates(device_updated)

        while True:
            await asyncio.sleep(0.1)


async def test_devices(init: bool, gen: int | None, dump: bool) -> None:
    """Test multiple devices."""
    device_options = []
    with open("devices.json", encoding="utf8") as fp:
        for line in fp:
            device_options.append(ConnectionOptions(**json.loads(line)))

    async with aiohttp.ClientSession() as aiohttp_session:
        results = await asyncio.gather(
            *[
                asyncio.gather(
                    connect_and_print_device(aiohttp_session, options, init, gen, dump),
                )
                for options in device_options
            ],
            return_exceptions=True,
        )

        for options, result in zip(device_options, results):
            if not isinstance(result, Exception):
                continue

            print()
            print(f"Error printing device @ {options.ip_address}")

            if isinstance(result, FirmwareUnsupported):
                print("Device firmware not supported")
            elif isinstance(result, InvalidAuthError):
                print("Invalid or missing authorization")
            elif isinstance(result, DeviceConnectionError):
                print("Error connecting to device")
            elif isinstance(result, MacAddressMismatchError):
                print("MAC address mismatch error")
            elif isinstance(result, WrongShellyGen):
                print("Wrong Shelly generation")
            else:
                print()
                traceback.print_tb(result.__traceback__)
                print(result)

        while True:
            await asyncio.sleep(0.1)


async def connect_and_print_device(
    aiohttp_session: aiohttp.ClientSession,
    options: ConnectionOptions,
    init: bool,
    gen: int | None,
    dump: bool,
) -> None:
    """Connect and print device data."""
    device = await create_device(aiohttp_session, options, init, gen)
    print_device(device, dump)
    device.subscribe_updates(device_updated)


def device_updated(
    cb_device: BlockDevice | RpcDevice, update_type: BlockUpdateType | RpcUpdateType
) -> None:
    """Device updated callback."""
    print()
    print(f"{datetime.now().strftime('%H:%M:%S')} Device updated! ({update_type})")
    try:
        print_device(cb_device, False)
    except InvalidAuthError:
        print("Invalid or missing authorization (from async init)")


def print_device(device: BlockDevice | RpcDevice, dump: bool) -> None:
    """Print device data."""
    if not device.initialized:
        print()
        print(f"** Device @ {device.ip_address} not initialized **")
        print()
        return

    model_name = MODEL_NAMES.get(device.model) or f"Unknown ({device.model})"
    print(f"** {device.name} - {model_name}  @ {device.ip_address} **")
    print()

    if dump:
        save_endpoints(device)

    if device.gen in BLOCK_GENERATIONS:
        print_block_device(cast(BlockDevice, device))
    elif device.gen in RPC_GENERATIONS:
        print_rpc_device(cast(RpcDevice, device))


def print_block_device(device: BlockDevice) -> None:
    """Print block (GEN1) device data."""
    assert device.blocks

    for block in device.blocks:
        print(block)
        for attr, value in block.current_values().items():
            info = block.info(attr)

            if value is None:
                value = "-"

            if BLOCK_VALUE_UNIT in info:
                unit = " " + info[BLOCK_VALUE_UNIT]
            else:
                unit = ""

            print(f"{attr.ljust(16)}{value}{unit}")
        print()


def print_rpc_device(device: RpcDevice) -> None:
    """Print RPC (GEN2/3) device data."""
    print(f"Status: {device.status}")
    print(f"Event: {device.event}")
    print(f"Connected: {device.connected}")


def save_endpoints(device: BlockDevice | RpcDevice) -> None:
    """Save device endpoints."""
    data_raw = {"shelly": device.shelly, "status": device.status}

    if device.gen in BLOCK_GENERATIONS:
        data_raw.update({"settings": device.settings})
        data_normalized = _normalize_block_data(data_raw)
    else:
        data_raw.update({"config": device.config})
        data_normalized = _normalize_rpc_data(data_raw)

    folder = "fixtures"
    if not os.path.exists(folder):
        os.makedirs(folder)
    with open(
        f"{folder}/gen{device.gen} - {device.model} - {MODEL_NAMES[device.model]}.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(data_normalized, file, ensure_ascii=False, indent=4)
        file.write("\n")
    sys.exit(0)


def _replacement_values() -> dict[str, Any]:
    return {
        "wifi": "Wifi-Network-Name",
        "wifi_mac": "11:22:33:44:55:66",
        "device_mac": "AABBCCDDEEFF",
        "device_name": "Test Name",
        "switch_name": "Switch Test Name",
        "input_name": "Input Test Name",
        "em_name": "Energy Monitor Test Name",
    }


def _normalize_block_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize data for BLOCK devices."""
    status = data["status"]
    shelly = data["shelly"]
    settings = data["settings"]
    values = _replacement_values()

    real_mac: str = status["mac"]

    # Shelly endpoint
    shelly["name"] = values["device_name"]
    shelly["mac"] = values["device_mac"]

    # Status endpoint
    status["mac"] = values["device_mac"]

    if status["wifi_sta"].get("ssid"):
        status["wifi_sta"]["ssid"] = values["wifi"]

    # Config endpoint
    settings["device"]["hostname"] = settings["device"]["hostname"].replace(
        real_mac, values["device_mac"]
    )
    settings["device"]["mac"] = values["device_mac"]

    # Some devices use MAC uppercase, others lowercase
    settings["mqtt"]["id"] = settings["mqtt"]["id"].replace(
        real_mac, values["device_mac"]
    )
    settings["mqtt"]["id"] = settings["mqtt"]["id"].replace(
        real_mac.lower(), values["device_mac"].lower()
    )

    settings["name"] = values["device_name"]
    settings["wifi_ap"]["ssid"] = settings["wifi_ap"]["ssid"].replace(
        real_mac, values["device_mac"]
    )
    settings["wifi_sta"]["ssid"] = values["wifi"]

    # Updata dataset
    data.update({"settings": settings})
    data.update({"shelly": shelly})
    data.update({"status": status})

    return data


def _normalize_rpc_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize data for RPC devices."""
    config = data["config"]
    status = data["status"]
    shelly = data["shelly"]

    real_mac: str = status["sys"]["mac"]

    values = _replacement_values()

    # Config endpoint
    config["sys"]["device"]["name"] = values["device_name"]
    config["sys"]["device"]["mac"] = values["device_mac"]

    # Some devices use MAC uppercase, others lowercase
    config["mqtt"]["client_id"] = config["mqtt"]["client_id"].replace(
        real_mac, values["device_mac"]
    )
    config["mqtt"]["client_id"] = config["mqtt"]["client_id"].replace(
        real_mac.lower(), values["device_mac"].lower()
    )

    if config["mqtt"].get("topic_prefix"):
        # Some devices use MAC uppercase, others lowercase
        config["mqtt"]["topic_prefix"] = config["mqtt"]["topic_prefix"].replace(
            real_mac, values["device_mac"]
        )
        config["mqtt"]["topic_prefix"] = config["mqtt"]["topic_prefix"].replace(
            real_mac.lower(), values["device_mac"].lower()
        )

    for id_ in range(5):
        if config.get(f"thermostat:{id_}"):
            config[f"thermostat:{id_}"]["sensor"] = config[f"thermostat:{id_}"][
                "sensor"
            ].replace(real_mac.lower(), values["device_mac"].lower())
            config[f"thermostat:{id_}"]["actuator"] = config[f"thermostat:{id_}"][
                "actuator"
            ].replace(real_mac.lower(), values["device_mac"].lower())

        if config.get(f"switch:{id_}"):
            config[f"switch:{id_}"]["name"] = f"{values['switch_name']} {id_}"

        if config.get(f"input:{id_}"):
            config[f"input:{id_}"]["name"] = f"{values['input_name']} {id_}"

        if config.get(f"em:{id_}"):
            config[f"em:{id_}"]["name"] = f"{values['em_name']} {id_}"

    if config.get("wifi"):
        config["wifi"] = values["wifi"]

    # Shelly endpoint
    shelly["name"] = values["device_name"]
    # Some devices use MAC uppercase, others lowercase
    shelly["id"] = shelly["id"].replace(real_mac, values["device_mac"])
    shelly["id"] = shelly["id"].replace(real_mac.lower(), values["device_mac"].lower())
    shelly["mac"] = values["device_mac"]

    # Status endpoint
    status["sys"]["mac"] = values["device_mac"]

    if status["wifi"].get("ssid"):
        status["wifi"]["ssid"] = values["wifi"]

    if status["wifi"].get("mac"):
        status["wifi"]["mac"] = values["wifi_mac"]

    if status["sys"].get("id"):
        # Some devices use MAC uppercase, others lowercase
        status["sys"]["id"] = status["sys"]["id"].replace(
            real_mac, values["device_mac"]
        )
        status["sys"]["id"] = status["sys"]["id"].replace(
            real_mac.lower(), values["device_mac"].lower()
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
        "--devices",
        "-d",
        action="store_true",
        help='Connect to all the devices in "devices.json" at once and print their status',
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

    parser.add_argument(
        "--update_ws",
        "-uw",
        type=str,
        help="Update outbound WebSocket (Gen2/3) and exit",
    )
    parser.add_argument(
        "--dump_device_info",
        "-di",
        action="store_true",
        help="Dump all endpoint to save fixtures",
    )

    arguments = parser.parse_args()

    return parser, arguments


async def update_outbound_ws(
    options: ConnectionOptions, init: bool, ws_url: str
) -> None:
    """Update outbound WebSocket URL (Gen2/3)."""
    async with aiohttp.ClientSession() as aiohttp_session:
        device: RpcDevice = await create_device(aiohttp_session, options, init, 2)
        print(f"Updating outbound weboskcet URL to {ws_url}")
        print(f"Restart required: {await device.update_outbound_websocket(ws_url)}")


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

    if args.devices:
        await test_devices(args.init, gen, args.dump_device_info)
    elif args.ip_address:
        if args.username and args.password is None:
            parser.error("--username and --password must be used together")
        options = ConnectionOptions(
            args.ip_address, args.username, args.password, device_mac=args.mac
        )
        if args.update_ws:
            await update_outbound_ws(options, args.init, args.update_ws)
        else:
            await test_single(options, args.init, gen, args.dump_device_info)
    else:
        parser.error("--ip_address or --devices must be specified")


if __name__ == "__main__":
    asyncio.run(main())
