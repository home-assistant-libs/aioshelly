"""Tests for const module."""

import pytest

from aioshelly.const import DEVICES, MODEL_NAMES


@pytest.mark.parametrize(
    ("model", "expected_name"),
    [
        ("SHSW-1", "Shelly 1"),
        ("SHSW-21", "Shelly 2"),
        ("SHSW-25", "Shelly 2.5"),
        ("SHSW-44", "Shelly 4Pro"),
    ],
)
def test_model_name(model: str, expected_name: str) -> None:
    """Test model name."""
    assert MODEL_NAMES[model] == expected_name
    assert DEVICES[model].name == expected_name
