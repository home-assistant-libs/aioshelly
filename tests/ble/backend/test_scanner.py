from unittest.mock import AsyncMock, patch

import pytest

from aioshelly.ble import create_scanner
from aioshelly.exceptions import RpcCallError


@pytest.mark.asyncio
async def test_create_scanner_back_compat() -> None:
    """Test create scanner works without modes."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    scanner.async_on_event(
        {
            "event": "ble.scan_result",
            "data": [
                2,
                [
                    [
                        "AA:BB:CC:DD:EE:FF",
                        -50,
                        "AQIDBAUGBwgJCg==",
                        "AQIDBAUGBwgJCg==",
                    ]
                ],
            ],
        }
    )
    scanner_data = scanner.discovered_devices_and_advertisement_data
    assert "AA:BB:CC:DD:EE:FF" in scanner_data
    ble_device, advertisement_data = scanner_data["AA:BB:CC:DD:EE:FF"]
    assert advertisement_data.rssi == -50
    assert ble_device.address == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_async_request_active_window_no_provider() -> None:
    """Without a bound device the request returns False without any RPC traffic."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    assert await scanner.async_request_active_window(0.0) is False


@pytest.mark.asyncio
async def test_async_request_active_window_flips_then_restores() -> None:
    """The Shelly is reprovisioned active then reverted to passive."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    device = AsyncMock()
    scanner.set_active_window_provider(device, "ble.scan_result", 2)
    with patch("aioshelly.ble.async_start_scanner", AsyncMock()) as mock_start:
        assert await scanner.async_request_active_window(0.0) is True
    actives = [call.kwargs["active"] for call in mock_start.await_args_list]
    assert actives == [True, False]


@pytest.mark.asyncio
async def test_async_request_active_window_entry_failure_returns_false() -> None:
    """A failure on the entry call yields False; no restore is attempted."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    device = AsyncMock()
    scanner.set_active_window_provider(device, "ble.scan_result", 2)
    mock_start = AsyncMock(side_effect=RpcCallError(500, "boom"))
    with patch("aioshelly.ble.async_start_scanner", mock_start):
        assert await scanner.async_request_active_window(0.0) is False
    assert mock_start.await_count == 1


@pytest.mark.asyncio
async def test_async_request_active_window_restore_failure_swallowed() -> None:
    """If the restore call fails the window still reports success."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    device = AsyncMock()
    scanner.set_active_window_provider(device, "ble.scan_result", 2)
    call_count = 0

    async def fake_start(*_args: object, **_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RpcCallError(500, "restore failed")

    with patch("aioshelly.ble.async_start_scanner", AsyncMock(side_effect=fake_start)):
        assert await scanner.async_request_active_window(0.0) is True
    assert call_count == 2
