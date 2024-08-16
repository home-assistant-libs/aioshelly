"""Tests for rpc_device.device module."""

from aioshelly.rpc_device.device import mergedicts


def test_mergedicts() -> None:
    """Test the recursive dict merge."""
    dest = {"a": 1, "b": {"c": 2, "d": 3}}
    source = {"b": {"c": 4, "e": 5}}
    mergedicts(dest, source)
    assert dest == {"a": 1, "b": {"c": 4, "d": 3, "e": 5}}
