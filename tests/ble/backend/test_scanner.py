import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from habluetooth import BluetoothScanningMode

from aioshelly.ble import create_scanner
from aioshelly.exceptions import DeviceConnectionError, RpcCallError


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


def _bind(scanner: object) -> AsyncMock:
    device = AsyncMock()
    scanner.set_active_window_provider(device)  # type: ignore[attr-defined]
    return device


@pytest.mark.asyncio
async def test_async_request_active_window_resolve_failure_returns_false() -> None:
    """A ShellyError while resolving the script id yields False without flipping."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    with (
        patch(
            "aioshelly.ble.async_get_ble_script_id",
            AsyncMock(side_effect=RpcCallError(500, "list failed")),
        ),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock()) as mock_set,
    ):
        assert await scanner.async_request_active_window(0.0) is False
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_request_active_window_no_script() -> None:
    """If the integration script isn't installed, return False without flipping."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=None)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock()) as mock_set,
    ):
        assert await scanner.async_request_active_window(0.0) is False
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_request_active_window_flips_then_restores() -> None:
    """The Shelly is flipped active then reverted to passive."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock()) as mock_set,
    ):
        assert await scanner.async_request_active_window(0.0) is True
    actives = [call.kwargs["active"] for call in mock_set.await_args_list]
    assert actives == [True, False]
    # script_id is passed positionally as the second arg.
    script_ids = [call.args[1] for call in mock_set.await_args_list]
    assert script_ids == [7, 7]


@pytest.mark.asyncio
async def test_async_request_active_window_caches_script_id() -> None:
    """Across two windows the script id is resolved exactly once."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    with (
        patch(
            "aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)
        ) as mock_get,
        patch("aioshelly.ble.async_set_active_mode", AsyncMock()),
    ):
        assert await scanner.async_request_active_window(0.0) is True
        assert await scanner.async_request_active_window(0.0) is True
    assert mock_get.await_count == 1


@pytest.mark.asyncio
async def test_async_request_active_window_entry_failure_returns_false() -> None:
    """A failure on the entry call yields False; no restore is attempted."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    mock_set = AsyncMock(side_effect=RpcCallError(500, "boom"))
    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", mock_set),
    ):
        assert await scanner.async_request_active_window(0.0) is False
    assert mock_set.await_count == 1


@pytest.mark.asyncio
async def test_async_request_active_window_restore_failure_swallowed() -> None:
    """If the restore call fails the window still reports success."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    call_count = 0

    async def fake_set(*_args: object, **_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RpcCallError(500, "restore failed")

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock(side_effect=fake_set)),
    ):
        assert await scanner.async_request_active_window(0.0) is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_request_active_window_entry_device_error_returns_false() -> None:
    """A DeviceConnectionError on entry yields False; the contract is bool-only."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    mock_set = AsyncMock(side_effect=DeviceConnectionError("disconnected"))
    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", mock_set),
    ):
        assert await scanner.async_request_active_window(0.0) is False
    assert mock_set.await_count == 1


@pytest.mark.asyncio
async def test_async_request_active_window_restore_device_error_swallowed() -> None:
    """A DeviceConnectionError on restore is swallowed, window still reports True."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    call_count = 0

    async def fake_set(*_args: object, **_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise DeviceConnectionError("disconnected mid-window")

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock(side_effect=fake_set)),
    ):
        assert await scanner.async_request_active_window(0.0) is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_request_active_window_rejects_overlap() -> None:
    """A second request while a window is open returns False without flipping."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)
    gate = asyncio.Event()

    async def fake_set(*_args: object, **kwargs: object) -> None:
        if kwargs.get("active"):
            await gate.wait()

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch(
            "aioshelly.ble.async_set_active_mode", AsyncMock(side_effect=fake_set)
        ) as mock_set,
    ):
        first = asyncio.create_task(scanner.async_request_active_window(0.0))
        # Yield so the first task acquires the lock and blocks inside the entry call.
        await asyncio.sleep(0)
        assert await scanner.async_request_active_window(0.0) is False
        # Only the first task has called async_set_active_mode (the entry flip).
        assert mock_set.await_count == 1
        gate.set()
        assert await first is True


@pytest.mark.asyncio
async def test_async_request_active_window_updates_current_mode() -> None:
    """During a window current_mode flips to ACTIVE then back to the prior value.

    The UI reads current_mode (via the manager's scanner_mode_changed
    notification), so without this the proxy keeps reporting passive
    while the Shelly is actually doing active sweeps.
    """
    scanner = create_scanner(
        "AA:BB:CC:DD:EE:FF",
        "shelly",
        requested_mode=BluetoothScanningMode.PASSIVE,
        current_mode=BluetoothScanningMode.PASSIVE,
    )
    _bind(scanner)
    observed: list[BluetoothScanningMode | None] = []

    async def fake_set(*_args: object, **_kwargs: object) -> None:
        observed.append(scanner.current_mode)

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock(side_effect=fake_set)),
    ):
        assert await scanner.async_request_active_window(0.0) is True
    # Entry RPC ran before the flip (pre-flip mode); restore RPC ran while
    # the window was open (so current_mode was ACTIVE at that point).
    assert observed == [BluetoothScanningMode.PASSIVE, BluetoothScanningMode.ACTIVE]
    assert scanner.current_mode is BluetoothScanningMode.PASSIVE


@pytest.mark.asyncio
async def test_active_window_restores_current_mode_on_restore_failure() -> None:
    """A failed restore still flips current_mode back so the UI doesn't lie forever."""
    scanner = create_scanner(
        "AA:BB:CC:DD:EE:FF",
        "shelly",
        requested_mode=BluetoothScanningMode.PASSIVE,
        current_mode=BluetoothScanningMode.PASSIVE,
    )
    _bind(scanner)
    call_count = 0

    async def fake_set(*_args: object, **_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RpcCallError(500, "restore failed")

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock(side_effect=fake_set)),
    ):
        assert await scanner.async_request_active_window(0.0) is True
    assert scanner.current_mode is BluetoothScanningMode.PASSIVE


@pytest.mark.asyncio
async def test_async_request_active_window_restore_runs_under_cancellation() -> None:
    """Cancelling the task during the window still fires the restore call."""
    scanner = create_scanner("AA:BB:CC:DD:EE:FF", "shelly")
    _bind(scanner)

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock()) as mock_set,
    ):
        task = asyncio.create_task(scanner.async_request_active_window(3600.0))
        # Let the entry call complete and the task enter the sleep.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    actives = [call.kwargs["active"] for call in mock_set.await_args_list]
    assert actives == [True, False]


@pytest.mark.asyncio
async def test_active_window_restores_current_mode_when_restore_is_cancelled() -> None:
    """Cancellation mid-restore still flips current_mode back to the prior value."""
    scanner = create_scanner(
        "AA:BB:CC:DD:EE:FF",
        "shelly",
        requested_mode=BluetoothScanningMode.PASSIVE,
        current_mode=BluetoothScanningMode.PASSIVE,
    )
    _bind(scanner)
    restore_started = asyncio.Event()

    async def fake_set(*_args: object, **kwargs: object) -> None:
        if not kwargs.get("active"):
            restore_started.set()
            await asyncio.sleep(3600)

    with (
        patch("aioshelly.ble.async_get_ble_script_id", AsyncMock(return_value=7)),
        patch("aioshelly.ble.async_set_active_mode", AsyncMock(side_effect=fake_set)),
    ):
        task = asyncio.create_task(scanner.async_request_active_window(0.0))
        await restore_started.wait()
        # Window is past entry; the restore RPC is in flight.
        assert scanner.current_mode is BluetoothScanningMode.ACTIVE
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert scanner.current_mode is BluetoothScanningMode.PASSIVE
