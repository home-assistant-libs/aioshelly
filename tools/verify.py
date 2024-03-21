"""Download and verify all Coiot examples from the Shelly website."""

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import Mock

import requests
import urllib3
from aiohttp.helpers import reify

from aioshelly.block_device import BLOCK_VALUE_UNIT, BlockDevice
from aioshelly.block_device.coap import CoapType
from aioshelly.common import ConnectionOptions
from aioshelly.const import DEVICE_IO_TIMEOUT

urllib3.disable_warnings()

BASE_URL = "https://shelly-api-docs.shelly.cloud/docs/coiot/v2/examples/"
_LOGGER = logging.getLogger(__name__)


@dataclass
class CoiotExample:
    """CoiotExample class."""

    filename: str

    _cache: dict = field(default_factory=dict)

    @reify
    def name(self) -> str:
        """Get filename."""
        return urllib.parse.unquote(self.filename)

    @reify
    def url(self) -> str:
        """Get file URL."""
        return BASE_URL + self.filename

    @reify
    def content(self) -> str:
        """Get file content."""
        return requests.get(self.url, timeout=DEVICE_IO_TIMEOUT, verify=False).text  # noqa: S501

    @reify
    def content_parsed(self) -> list[dict[str, Any]]:
        """Parse file."""
        lines = self.content.split("\n")
        parsed = []

        start = None

        for i, line in enumerate(lines):
            if line.rstrip() == "{":
                start = i
            elif line.rstrip() == "}":
                parsed.append(lines[start : i + 1])

        if len(parsed) != 2:  # noqa: PLR2004
            raise ValueError("Uuh, not length 2")

        processed = []

        for value in parsed:
            text = "\n".join(value).strip()
            try:
                processed.append(json.loads(text))
            except ValueError:
                _LOGGER.error("Error parsing %s", self.url)
                _LOGGER.exception(text)
                raise

        return processed

    @reify
    def cit_s(self) -> dict[str, Any]:
        """Return parsed cit/s."""
        return self.content_parsed[0]

    @reify
    def cit_d(self) -> dict[str, Any]:
        """Return parsed cit/d."""
        return self.content_parsed[1]

    @reify
    def device(self) -> BlockDevice:
        """Create mocked device."""
        device = BlockDevice(Mock(), None, ConnectionOptions("mock-ip"))
        device._update_d(self.cit_d)  # noqa: SLF001
        device._update_s(self.cit_s, CoapType.REPLY)  # noqa: SLF001
        return device


def coiot_examples() -> list[CoiotExample]:
    """Get coiot examples."""
    index = requests.get(
        BASE_URL,
        # Not sure, local machine barfs on their cert
        timeout=DEVICE_IO_TIMEOUT,
        verify=False,  # noqa: S501
    ).text
    return [
        CoiotExample(match)
        for match in re.findall(r'href="(.+?)"', index)
        if match.startswith("Shelly")
    ]


def print_example(example: CoiotExample) -> None:
    """Print example."""
    print(example.name)
    print()

    for block in example.device.blocks:
        print(block)
        for attr, value in block.current_values().items():
            info = block.info(attr)

            _value = value if value is not None else "None"

            unit = " " + info[BLOCK_VALUE_UNIT] if BLOCK_VALUE_UNIT in info else ""

            print(f"{attr.ljust(16)}{_value}{unit}")
        print()

    print("-" * 32)
    print()


def run() -> None:
    """Run coiot_examples and print errors."""
    errors = []
    for example in coiot_examples():
        try:
            print_example(example)
        except Exception as err:  # noqa: BLE001
            errors.append((example, err))
            break

    for example, err in errors:
        print("Error fetching", example.name)
        print(example.url)
        print()
        _LOGGER.error("", exc_info=err)
        print()
        print("-" * 32)
        print()


if __name__ == "__main__":
    run()
