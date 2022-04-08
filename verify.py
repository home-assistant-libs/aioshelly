"""Verify script that downloads all Coiot examples from the Shelly website and checks to make sure that we can parse them."""
import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from unittest.mock import Mock

import requests
import urllib3
from aiohttp.helpers import reify

import aioshelly

urllib3.disable_warnings()

BASE_URL = "https://shelly-api-docs.shelly.cloud/docs/coiot/v2/examples/"
_LOGGER = logging.getLogger(__name__)


@dataclass
class CoiotExample:
    """CoiotExample class."""

    filename: str

    _cache: dict = field(default_factory=dict)

    @reify
    def name(self):
        """Get filename."""
        return urllib.parse.unquote(self.filename)

    @reify
    def url(self):
        """Get file URL."""
        return BASE_URL + self.filename

    @reify
    def content(self):
        """Get file content."""
        return requests.get(self.url, verify=False).text

    @reify
    def content_parsed(self):
        """Parse file."""
        lines = self.content.split("\n")
        parsed = []

        start = None

        for i, line in enumerate(lines):
            if line.rstrip() == "{":
                start = i
            elif line.rstrip() == "}":
                parsed.append(lines[start : i + 1])

        if len(parsed) != 2:
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
    def cit_s(self):
        """Return parsed cit/s."""
        return self.content_parsed[0]

    @reify
    def cit_d(self):
        """Return parsed cit/d."""
        return self.content_parsed[1]

    @reify
    def device(self):
        """Create mocked device."""
        device = aioshelly.Device(Mock(), None, aioshelly.ConnectionOptions("mock-ip"))
        device._update_d(self.cit_d)
        device._update_s(self.cit_s)
        return device


def coiot_examples():
    """Get coiot examples."""
    index = requests.get(
        BASE_URL,
        # Not sure, local machine barfs on their cert
        verify=False,
    ).text
    return [
        CoiotExample(match)
        for match in re.findall(r'href="(.+?)"', index)
        if match.startswith("Shelly")
    ]


def print_example(example):
    """Print example."""
    print(example.name)
    print()

    for block in example.device.blocks:
        print(block)
        for attr, value in block.current_values().items():
            info = block.info(attr)

            if value is None:
                value = "None"

            if aioshelly.BLOCK_VALUE_UNIT in info:
                unit = " " + info[aioshelly.BLOCK_VALUE_UNIT]
            else:
                unit = ""

            print(f"{attr.ljust(16)}{value}{unit}")
        print()

    print("-" * 32)
    print()


def run():
    """Run coiot_examples and print errors."""
    errors = []
    for example in coiot_examples():
        try:
            print_example(example)
        except Exception as err:
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
