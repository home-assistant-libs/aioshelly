"""Tests for the BLE parser."""

from __future__ import annotations

import pytest

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


def test_parse_unsupported_version() -> None:
    """Test parse raises on unsupported version."""
    with pytest.raises(ValueError, match="Unsupported BLE scan result version: 3"):
        parse_ble_scan_result_event([3, []])


def test_parse_x2i_v2() -> None:
    """Test Wall Display X2i object-based BLE scan result."""
    assert parse_ble_scan_result_event(
        {
            "version": 2,
            "packets": [
                [
                    "AA:BB:CC:DD:EE:FF",
                    -90,
                    "DRbS/EAA8gFkLjJF7QA=",
                    "",
                ],
            ],
        }
    ) == [
        (
            "AA:BB:CC:DD:EE:FF",
            -90,
            bytes.fromhex("0d16d2fc4000f201642e3245ed00"),
        )
    ]


def test_parse_x2i_empty_packets() -> None:
    """Test Wall Display X2i empty scan result."""
    assert parse_ble_scan_result_event({"version": 2, "packets": []}) == []


def test_parse_x2i_unsupported_version() -> None:
    """Test Wall Display X2i unsupported scan result version."""
    with pytest.raises(ValueError, match="Unsupported BLE scan result version: 3"):
        parse_ble_scan_result_event({"version": 3, "packets": []})
