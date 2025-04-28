"""Tests for the BLE parser."""

from __future__ import annotations

from aioshelly.ble.parser import parse_ble_scan_result_event


def test_parse_v1() -> None:
    """Test parse v1."""
    assert parse_ble_scan_result_event(
        [
            1,
            "AA:BB:CC:DD:EE:FF",
            -50,
            "AQIDBAUGBwgJCg==",
            "AQIDBAUGBwgJCg==",
        ]
    ) == [
        (
            "AA:BB:CC:DD:EE:FF",
            -50,
            b"\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x01\x02\x03\x04\x05\x06\x07\x08\t\n",
        )
    ]


def test_parse_v2() -> None:
    """Test parse v2."""
    assert parse_ble_scan_result_event(
        [
            2,
            [
                [
                    "AA:BB:CC:DD:EE:FF",
                    -50,
                    "AQIDBAUGBwgJCg==",
                    "AQIDBAUGBwgJCg==",
                ],
                [
                    "AA:BB:CC:DD:EE:FF",
                    -50,
                    "AQIDBAUGBwgJCg==",
                    "AQIDBAUGBwgJCg==",
                ],
            ],
        ]
    ) == [
        (
            "AA:BB:CC:DD:EE:FF",
            -50,
            b"\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x01\x02\x03\x04\x05\x06\x07\x08\t\n",
        ),
        (
            "AA:BB:CC:DD:EE:FF",
            -50,
            b"\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x01\x02\x03\x04\x05\x06\x07\x08\t\n",
        ),
    ]
