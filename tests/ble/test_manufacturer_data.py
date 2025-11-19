"""Tests for the BLE manufacturer data parser."""

from __future__ import annotations

from aioshelly.ble.manufacturer_data import (
    ALLTERCO_MFID,
    BLOCK_TYPE_FLAGS,
    BLOCK_TYPE_MAC,
    BLOCK_TYPE_MODEL,
    has_rpc_over_ble,
    parse_shelly_manufacturer_data,
)


def test_parse_empty_manufacturer_data() -> None:
    """Test parsing empty manufacturer data."""
    assert parse_shelly_manufacturer_data({}) is None


def test_parse_wrong_manufacturer_id() -> None:
    """Test parsing manufacturer data with wrong ID."""
    assert parse_shelly_manufacturer_data({0x1234: b"\x01\x02\x03"}) is None


def test_parse_too_short_data() -> None:
    """Test parsing manufacturer data that is too short."""
    assert parse_shelly_manufacturer_data({ALLTERCO_MFID: b""}) is None


def test_parse_flags_only() -> None:
    """Test parsing manufacturer data with flags only."""
    # Block type 0x01 (flags) + 2 bytes flags (0x0004 = RPC over BLE enabled)
    data = bytes([BLOCK_TYPE_FLAGS, 0x04, 0x00])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    assert result == {"flags": 0x0004}


def test_parse_mac_only() -> None:
    """Test parsing manufacturer data with MAC address only."""
    # Block type 0x0A (MAC) + 6 bytes MAC address (stored in reverse order)
    data = bytes([BLOCK_TYPE_MAC, 0xC0, 0x49, 0xEF, 0x88, 0x73, 0xE8])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # MAC bytes are reversed when parsed
    assert result == {"mac": "E8:73:88:EF:49:C0"}


def test_parse_model_only() -> None:
    """Test parsing manufacturer data with model ID only."""
    # Block type 0x0B (model) + 2 bytes model ID (0x1234)
    data = bytes([BLOCK_TYPE_MODEL, 0x34, 0x12])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    assert result == {"model_id": 0x1234}


def test_parse_all_blocks() -> None:
    """Test parsing manufacturer data with all block types."""
    # Flags + MAC + Model
    data = bytes(
        [
            BLOCK_TYPE_FLAGS,
            0x07,
            0x00,  # flags = 0x0007 (discoverable, auth, RPC over BLE)
            BLOCK_TYPE_MAC,
            0xC0,
            0x49,
            0xEF,
            0x88,
            0x73,
            0xE8,  # MAC (stored in reverse order)
            BLOCK_TYPE_MODEL,
            0x34,
            0x12,  # model = 0x1234
        ]
    )
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    assert result == {
        "flags": 0x0007,
        "mac": "E8:73:88:EF:49:C0",  # MAC bytes are reversed when parsed
        "model_id": 0x1234,
    }


def test_parse_truncated_flags() -> None:
    """Test parsing manufacturer data with truncated flags block."""
    # Block type 0x01 (flags) but only 1 byte of data (needs 2)
    data = bytes([BLOCK_TYPE_FLAGS, 0x04])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # Should stop parsing and return empty result
    assert result is None


def test_parse_truncated_mac() -> None:
    """Test parsing manufacturer data with truncated MAC block."""
    # Block type 0x0A (MAC) but only 3 bytes (needs 6)
    data = bytes([BLOCK_TYPE_MAC, 0xC0, 0x49, 0xEF])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # Should stop parsing and return empty result
    assert result is None


def test_parse_truncated_model() -> None:
    """Test parsing manufacturer data with truncated model block."""
    # Block type 0x0B (model) but only 1 byte (needs 2)
    data = bytes([BLOCK_TYPE_MODEL, 0x34])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # Should stop parsing and return empty result
    assert result is None


def test_parse_partial_blocks() -> None:
    """Test parsing with valid block followed by incomplete block."""
    # Valid flags block followed by incomplete MAC block
    data = bytes([BLOCK_TYPE_FLAGS, 0x04, 0x00, BLOCK_TYPE_MAC, 0xC0, 0x49])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # Should parse flags but stop at incomplete MAC
    assert result == {"flags": 0x0004}


def test_parse_lone_block_type() -> None:
    """Test parsing with lone block type byte at end (no data following)."""
    # Valid flags block followed by MODEL block type with no data
    data = bytes([BLOCK_TYPE_FLAGS, 0x04, 0x00, BLOCK_TYPE_MODEL])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # Should parse flags but stop at MODEL block that has no data
    assert result == {"flags": 0x0004}


def test_parse_unknown_block_type() -> None:
    """Test parsing manufacturer data with unknown block type."""
    # Flags + unknown block type 0xFF
    data = bytes([BLOCK_TYPE_FLAGS, 0x04, 0x00, 0xFF, 0x01, 0x02])
    result = parse_shelly_manufacturer_data({ALLTERCO_MFID: data})
    # Should parse flags and stop at unknown block
    assert result == {"flags": 0x0004}


def test_has_rpc_over_ble_enabled() -> None:
    """Test checking if RPC over BLE is enabled."""
    # RPC over BLE enabled (bit 2 = 0x04)
    data = bytes([BLOCK_TYPE_FLAGS, 0x04, 0x00])
    assert has_rpc_over_ble({ALLTERCO_MFID: data}) is True


def test_has_rpc_over_ble_disabled() -> None:
    """Test checking if RPC over BLE is disabled."""
    # RPC over BLE disabled (only bits 0 and 1 set)
    data = bytes([BLOCK_TYPE_FLAGS, 0x03, 0x00])
    assert has_rpc_over_ble({ALLTERCO_MFID: data}) is False


def test_has_rpc_over_ble_no_flags() -> None:
    """Test checking RPC over BLE with no flags block."""
    # Only MAC, no flags
    data = bytes([BLOCK_TYPE_MAC, 0xC0, 0x49, 0xEF, 0x88, 0x73, 0xE8])
    assert has_rpc_over_ble({ALLTERCO_MFID: data}) is False


def test_has_rpc_over_ble_empty_data() -> None:
    """Test checking RPC over BLE with empty data."""
    assert has_rpc_over_ble({}) is False


def test_has_rpc_over_ble_wrong_manufacturer() -> None:
    """Test checking RPC over BLE with wrong manufacturer ID."""
    data = bytes([BLOCK_TYPE_FLAGS, 0x04, 0x00])
    assert has_rpc_over_ble({0x1234: data}) is False
