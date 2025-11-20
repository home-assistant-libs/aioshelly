"""Tests for rpc_device.blerpc module."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from aioshelly.exceptions import (
    BleCharacteristicNotFoundError,
    BleConnectionError,
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    RpcCallError,
)
from aioshelly.json import json_bytes
from aioshelly.rpc_device import blerpc
from aioshelly.rpc_device.blerpc import (
    DATA_CHARACTERISTIC_UUID,
    RPC_SERVICE_UUID,
    RX_POLL_MAX_ATTEMPTS,
    BleRPC,
)


@pytest.fixture
def ble_device() -> BLEDevice:
    """Create mock BLE device."""
    device = MagicMock(spec=BLEDevice)
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "ShellyPlus1-Test"
    return device


@pytest.fixture
def mock_ble_client() -> MagicMock:
    """Create mock BLE client."""
    client = AsyncMock()
    client.is_connected = True

    # Mock services with characteristics
    service = Mock()
    characteristic = Mock()
    characteristic.uuid = DATA_CHARACTERISTIC_UUID

    services = Mock()
    services.get_service.return_value = service
    services.get_characteristic.return_value = characteristic
    client.services = services

    return client


@pytest.fixture
def mock_establish_connection(mock_ble_client: MagicMock) -> Any:
    """Patch establish_connection to return mock client."""
    with patch(
        "aioshelly.rpc_device.blerpc.establish_connection",
        return_value=mock_ble_client,
    ) as mock_conn:
        yield mock_conn


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_connect(ble_device: BLEDevice) -> None:
    """Test BLE RPC connection."""
    ble_rpc = BleRPC(ble_device)
    await ble_rpc.connect()
    assert ble_rpc.connected is True


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_connect_already_connected(ble_device: BLEDevice) -> None:
    """Test BLE RPC connect when already connected."""
    ble_rpc = BleRPC(ble_device)
    await ble_rpc.connect()

    with pytest.raises(RuntimeError, match="Already connected"):
        await ble_rpc.connect()


@pytest.mark.asyncio
async def test_blerpc_connect_failure(
    ble_device: BLEDevice, mock_establish_connection: MagicMock
) -> None:
    """Test BLE RPC connection failure."""
    ble_rpc = BleRPC(ble_device)
    mock_establish_connection.side_effect = BleakError("Connection failed")

    with pytest.raises(BleConnectionError, match="Failed to connect"):
        await ble_rpc.connect()


@pytest.mark.asyncio
async def test_blerpc_connect_missing_characteristic(
    ble_device: BLEDevice, mock_establish_connection: MagicMock
) -> None:
    """Test BLE RPC connection with missing characteristic."""
    ble_rpc = BleRPC(ble_device)

    client = AsyncMock()
    client.is_connected = True

    # Mock services but missing characteristic
    service = Mock()
    services = Mock()
    services.get_service.return_value = service
    services.get_characteristic.return_value = None  # Missing characteristic
    client.services = services
    client.clear_cache = AsyncMock()
    client.disconnect = AsyncMock()

    mock_establish_connection.return_value = client

    with pytest.raises(BleCharacteristicNotFoundError):
        await ble_rpc.connect()

    # Should have tried twice (with cache clear)
    assert client.clear_cache.call_count == 1
    assert client.disconnect.call_count == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_disconnect(ble_device: BLEDevice) -> None:
    """Test BLE RPC disconnection."""
    ble_rpc = BleRPC(ble_device)
    await ble_rpc.connect()
    assert ble_rpc.connected is True

    await ble_rpc.disconnect()
    assert ble_rpc.connected is False


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call(ble_device: BLEDevice, mock_ble_client: MagicMock) -> None:
    """Test BLE RPC call."""
    # Create mock RPC response
    mock_response: dict[str, Any] = {
        "id": 1,
        "result": {"name": "Test Device", "model": "Test"},
    }
    ble_rpc = BleRPC(ble_device)

    # Mock GATT operations
    response_data = json_bytes(mock_response)
    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control (frame length)
    frame_length = len(response_data)
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),  # RX control returns length
        response_data,  # Data characteristic returns response
    ]

    await ble_rpc.connect()
    result = await ble_rpc.call("Shelly.GetDeviceInfo")

    assert result == mock_response["result"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_with_params(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with parameters."""
    # Create mock RPC response
    mock_response: dict[str, Any] = {
        "id": 1,
        "result": {"wifi": {"enable": True}, "sys": {"device": {"name": "Test"}}},
    }
    ble_rpc = BleRPC(ble_device)

    # Mock GATT operations
    response_data = json_bytes(mock_response)
    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control (frame length) and data
    frame_length = len(response_data)
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),
        response_data,
    ]

    await ble_rpc.connect()
    result = await ble_rpc.call("Shelly.GetConfig", {"id": 0})

    assert result == mock_response["result"]


@pytest.mark.asyncio
async def test_blerpc_call_not_connected(ble_device: BLEDevice) -> None:
    """Test BLE RPC call when not connected."""
    ble_rpc = BleRPC(ble_device)

    with pytest.raises(DeviceConnectionError, match="Not connected"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_timeout(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call timeout."""
    ble_rpc = BleRPC(ble_device)

    # Mock GATT operations that never return
    async def slow_read(*args: Any, **kwargs: Any) -> bytes:  # noqa: ARG001
        await asyncio.sleep(1)  # Sleep longer than timeout
        return b""

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock(side_effect=slow_read)

    await ble_rpc.connect()

    with pytest.raises(DeviceConnectionTimeoutError, match="timed out"):
        await ble_rpc.call("Shelly.GetDeviceInfo", timeout=0.01)


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_error_response(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with error response."""
    ble_rpc = BleRPC(ble_device)

    # Mock error response
    error_response: dict[str, Any] = {
        "id": 1,
        "error": {"code": 404, "message": "Not found"},
    }
    response_data = json_bytes(error_response)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    frame_length = len(response_data)
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),
        response_data,
    ]

    await ble_rpc.connect()

    with pytest.raises(RpcCallError, match="Not found"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_chunked_response(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with chunked response (>254 bytes)."""
    # Create large mock response (> 254 bytes to trigger chunking)
    large_result = {"data": "x" * 300, "name": "Test Device"}
    mock_response: dict[str, Any] = {
        "id": 1,
        "result": large_result,
    }
    ble_rpc = BleRPC(ble_device)

    # Mock GATT operations
    response_data = json_bytes(mock_response)
    frame_length = len(response_data)

    # Split response into chunks (simulate BLE characteristic size limit)
    chunk_size = 254
    chunks = [
        response_data[i : i + chunk_size]
        for i in range(0, len(response_data), chunk_size)
    ]

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control returns frame length, then each chunk
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),
        *chunks,
    ]

    await ble_rpc.connect()
    result = await ble_rpc.call("Shelly.GetDeviceInfo")

    assert result == large_result


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_incomplete_data(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with incomplete data."""
    ble_rpc = BleRPC(ble_device)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control says 1000 bytes, but only return 100 bytes then empty
    mock_ble_client.read_gatt_char.side_effect = [
        (1000).to_bytes(4, "big"),  # Says 1000 bytes available
        b"x" * 100,  # Only 100 bytes returned
        b"",  # Empty chunk (no more data)
    ]

    await ble_rpc.connect()

    with pytest.raises(DeviceConnectionError, match="Incomplete data"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_corrupted_frame_length_valid_json(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with corrupted frame length but valid complete JSON.

    Workaround for firmware bug where RX control returns wrong frame length
    but the actual data is complete valid JSON.
    """
    ble_rpc = BleRPC(ble_device)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    response = {"id": 1, "src": "test", "result": {"name": "Test Device"}}
    response_bytes = json.dumps(response).encode()

    # Mock RX control says 840106079 bytes (corrupted), but we get complete JSON
    mock_ble_client.read_gatt_char.side_effect = [
        (840106079).to_bytes(4, "big"),  # Corrupted frame length
        response_bytes,  # Complete valid JSON response
        b"",  # Empty chunk (no more data)
    ]

    await ble_rpc.connect()

    # Should succeed despite corrupted frame length because JSON is valid
    result = await ble_rpc.call("Shelly.GetDeviceInfo")
    assert result == {"name": "Test Device"}


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_invalid_json(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with invalid JSON response."""
    ble_rpc = BleRPC(ble_device)

    # Mock GATT operations with invalid JSON
    invalid_json = b"not valid json"
    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    frame_length = len(invalid_json)
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),
        invalid_json,
    ]

    await ble_rpc.connect()

    with pytest.raises(DeviceConnectionError, match="Invalid JSON"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_id_mismatch(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with response ID mismatch."""
    ble_rpc = BleRPC(ble_device)

    # Mock response with wrong ID
    wrong_id_response: dict[str, Any] = {
        "id": 999,  # Wrong ID
        "result": {"test": "data"},
    }
    response_data = json_bytes(wrong_id_response)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    frame_length = len(response_data)
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),
        response_data,
    ]

    await ble_rpc.connect()

    with pytest.raises(RpcCallError, match="Response ID mismatch"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
async def test_blerpc_connect_missing_rpc_service(
    ble_device: BLEDevice, mock_establish_connection: MagicMock
) -> None:
    """Test BLE RPC connection with missing RPC service."""
    ble_rpc = BleRPC(ble_device)

    client = AsyncMock()
    client.is_connected = True

    # Mock services but missing RPC service
    services = Mock()
    services.get_service.return_value = None  # Missing RPC service
    client.services = services
    client.clear_cache = AsyncMock()
    client.disconnect = AsyncMock()

    mock_establish_connection.return_value = client

    with pytest.raises(
        BleCharacteristicNotFoundError,
        match=f"RPC service {RPC_SERVICE_UUID} not found",
    ):
        await ble_rpc.connect()

    # Should have tried twice (with cache clear)
    assert client.clear_cache.call_count == 1
    assert client.disconnect.call_count == 2


@pytest.mark.asyncio
async def test_blerpc_connect_service_discovery_error(
    ble_device: BLEDevice, mock_establish_connection: MagicMock
) -> None:
    """Test BLE RPC connection with service discovery error."""
    ble_rpc = BleRPC(ble_device)

    client = AsyncMock()
    client.is_connected = True

    # Mock services that raises BleakError during access
    client.services = Mock()
    client.services.get_service.side_effect = BleakError("Service discovery failed")
    client.disconnect = AsyncMock()

    mock_establish_connection.return_value = client

    with pytest.raises(BleConnectionError, match="Failed to verify RPC service"):
        await ble_rpc.connect()

    # Should have disconnected
    assert client.disconnect.call_count == 1


@pytest.mark.asyncio
async def test_blerpc_connect_os_error(
    ble_device: BLEDevice, mock_establish_connection: MagicMock
) -> None:
    """Test BLE RPC connection with OS error during service discovery."""
    ble_rpc = BleRPC(ble_device)

    client = AsyncMock()
    client.is_connected = True

    # Mock services that raises OSError during access
    client.services = Mock()
    client.services.get_service.side_effect = OSError("OS error")
    client.disconnect = AsyncMock()

    mock_establish_connection.return_value = client

    with pytest.raises(BleConnectionError, match="Failed to verify RPC service"):
        await ble_rpc.connect()

    # Should have disconnected
    assert client.disconnect.call_count == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_disconnect_callback(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC disconnect callback."""
    ble_rpc = BleRPC(ble_device)

    await ble_rpc.connect()
    assert ble_rpc.connected is True

    # Simulate disconnect callback being called
    ble_rpc._on_disconnect(mock_ble_client)

    assert ble_rpc.connected is False


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_invalid_response(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with response that has neither error nor result."""
    ble_rpc = BleRPC(ble_device)

    # Mock response with neither error nor result
    invalid_response: dict[str, Any] = {
        "id": 1,
        # No error or result field
    }
    response_data = json_bytes(invalid_response)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    frame_length = len(response_data)
    mock_ble_client.read_gatt_char.side_effect = [
        frame_length.to_bytes(4, "big"),
        response_data,
    ]

    await ble_rpc.connect()

    with pytest.raises(RpcCallError, match="Invalid response"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_zero_frame_length_timeout(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with zero frame length that times out after polling."""
    ble_rpc = BleRPC(ble_device)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control always returns frame length of 0 (never ready)
    mock_ble_client.read_gatt_char.side_effect = [
        (0).to_bytes(4, "big")
    ] * RX_POLL_MAX_ATTEMPTS

    await ble_rpc.connect()

    # Patch RX_POLL_INTERVAL to 0 to avoid slow test
    with (
        patch.object(blerpc, "RX_POLL_INTERVAL", 0),
        pytest.raises(
            DeviceConnectionError,
            match=(
                f"No response data available after {RX_POLL_MAX_ATTEMPTS} poll attempts"
            ),
        ),
    ):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_zero_frame_length_then_success(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with zero frame length that eventually succeeds."""
    ble_rpc = BleRPC(ble_device)

    response_data = b'{"id":1,"result":{"name":"Test Device"}}'

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control returns 0 a few times, then actual frame length
    mock_ble_client.read_gatt_char.side_effect = [
        (0).to_bytes(4, "big"),  # First poll: not ready
        (0).to_bytes(4, "big"),  # Second poll: not ready
        len(response_data).to_bytes(4, "big"),  # Third poll: ready
        response_data,  # Data read
    ]

    await ble_rpc.connect()

    # Patch RX_POLL_INTERVAL to 0 to avoid slow test
    with patch.object(blerpc, "RX_POLL_INTERVAL", 0):
        result = await ble_rpc.call("Shelly.GetDeviceInfo")

    assert result == {"name": "Test Device"}


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_invalid_frame_length_data(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with invalid frame length data."""
    ble_rpc = BleRPC(ble_device)

    mock_ble_client.write_gatt_char = AsyncMock()
    mock_ble_client.read_gatt_char = AsyncMock()

    # Mock RX control returns insufficient bytes
    mock_ble_client.read_gatt_char.side_effect = [
        b"\x00\x00",  # Only 2 bytes instead of 4
    ]

    await ble_rpc.connect()

    with pytest.raises(DeviceConnectionError, match="Invalid frame length data"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
async def test_blerpc_disconnect_when_not_connected(ble_device: BLEDevice) -> None:
    """Test disconnect when client is None."""
    ble_rpc = BleRPC(ble_device)

    # Should not raise an error
    await ble_rpc.disconnect()
    assert ble_rpc.connected is False


@pytest.mark.asyncio
async def test_blerpc_verify_rpc_service_no_client(ble_device: BLEDevice) -> None:
    """Test _verify_rpc_service when client is None."""
    ble_rpc = BleRPC(ble_device)

    # _client is None, should raise RuntimeError
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await ble_rpc._verify_rpc_service()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_bleak_error(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with BleakError during transmission."""
    ble_rpc = BleRPC(ble_device)

    # Mock write_gatt_char to raise BleakError
    mock_ble_client.write_gatt_char = AsyncMock(
        side_effect=BleakError("Bluetooth error")
    )

    await ble_rpc.connect()

    with pytest.raises(DeviceConnectionError, match="BLE RPC call failed"):
        await ble_rpc.call("Shelly.GetDeviceInfo")


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_establish_connection")
async def test_blerpc_call_os_error(
    ble_device: BLEDevice, mock_ble_client: MagicMock
) -> None:
    """Test BLE RPC call with OSError during transmission."""
    ble_rpc = BleRPC(ble_device)

    # Mock write_gatt_char to raise OSError
    mock_ble_client.write_gatt_char = AsyncMock(side_effect=OSError("IO error"))

    await ble_rpc.connect()

    with pytest.raises(DeviceConnectionError, match="BLE RPC call failed"):
        await ble_rpc.call("Shelly.GetDeviceInfo")
