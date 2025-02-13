"""Tests for JSON helper."""

import pytest

from aioshelly.json import json_bytes, json_dumps


def test_json_bytes_with_dict() -> None:
    """Test json_bytes with a dict and non-str keys."""
    data = {"id": 1, "method": "Shelly.GetDeviceInfo", 3: "test"}
    result = json_bytes(data)

    assert isinstance(result, bytes)
    assert result == b'{"id":1,"method":"Shelly.GetDeviceInfo","3":"test"}'


def test_json_bytes_with_set() -> None:
    """Test json_bytes with a set."""
    data = {1, 2}
    result = json_bytes(data)

    assert isinstance(result, bytes)
    assert result in [b"[1,2]", b"[2,1]"]


def test_json_bytes_with_tuple() -> None:
    """Test json_bytes with a tuple."""
    data = (1, 2, 3)
    result = json_bytes(data)

    assert isinstance(result, bytes)
    assert result == b"[1,2,3]"


def test_json_bytes_with_non_serializable() -> None:
    """Test json_bytes with non-serializable object."""
    with pytest.raises(TypeError):
        json_bytes(object())


def test_json_dumps_with_dict() -> None:
    """Test json_dumps with a dict and non-str keys."""
    data = {"id": 1, "method": "Shelly.GetDeviceInfo", 3: "test"}
    result = json_dumps(data)

    assert isinstance(result, str)
    assert result == '{"id":1,"method":"Shelly.GetDeviceInfo","3":"test"}'


def test_json_dumps_with_set() -> None:
    """Test json_dumps with a set."""
    data = {1, 2}
    result = json_dumps(data)

    assert isinstance(result, str)
    assert result in ["[1,2]", "[2,1]"]


def test_json_dumps_with_tuple() -> None:
    """Test json_dumps with a tuple."""
    data = (1, 2, 3)
    result = json_dumps(data)

    assert isinstance(result, str)
    assert result == "[1,2,3]"


def test_json_dumps_with_non_serializable() -> None:
    """Test json_dumps with non-serializable object."""
    with pytest.raises(TypeError):
        json_dumps(object())
