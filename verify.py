import logging
import re
import json
from aiohttp.helpers import reify
from dataclasses import dataclass, field
from pprint import pprint
import requests
import urllib3
import urllib.parse

import aioshelly

urllib3.disable_warnings()

BASE_URL = "https://shelly-api-docs.shelly.cloud/docs/coiot/v2/examples/"
_LOGGER = logging.getLogger(__name__)


@dataclass
class CoiotExample:
    filename: str

    _cache: dict = field(default_factory=dict)

    @reify
    def name(self):
        return urllib.parse.unquote(self.filename)

    @reify
    def url(self):
        return BASE_URL + self.filename

    @reify
    def content(self):
        return requests.get(self.url, verify=False).text

    @reify
    def content_parsed(self):
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
        return self.content_parsed[0]

    @reify
    def cit_d(self):
        return self.content_parsed[1]

    @reify
    def device(self):
        device = aioshelly.Device(None, None, aioshelly.ConnectionOptions("mock-ip"))
        device._update_d(self.cit_d)
        device._update_s(self.cit_s)
        return device


def coiot_examples():
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
