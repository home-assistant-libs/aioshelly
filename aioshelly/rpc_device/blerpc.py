"""BLE RPC for Shelly devices."""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import TYPE_CHECKING, Any, cast

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

if TYPE_CHECKING:
    from bleak import BLEDevice

from ..const import DEVICE_IO_TIMEOUT
from ..exceptions import (
    BleCharacteristicNotFoundError,
    BleConnectionError,
    DeviceConnectionError,
    DeviceConnectionTimeoutError,
    RpcCallError,
)
from ..json import json_bytes, json_loads

_LOGGER = logging.getLogger(__name__)

# BLE GATT Service and Characteristic UUIDs for Shelly RPC
RPC_SERVICE_UUID = "5f6d4f53-5f52-5043-5f53-56435f49445f"
DATA_CHARACTERISTIC_UUID = "5f6d4f53-5f52-5043-5f64-6174615f5f5f"
TX_CONTROL_CHARACTERISTIC_UUID = "5f6d4f53-5f52-5043-5f74-785f63746c5f"
RX_CONTROL_CHARACTERISTIC_UUID = "5f6d4f53-5f52-5043-5f72-785f63746c5f"

# Protocol constants
UINT32_BYTES = 4  # Size of uint32 in bytes
MAX_CONNECTION_RETRIES = 2  # Initial attempt + 1 retry for cache issues
RX_POLL_INTERVAL = 0.1  # Seconds to wait between RX frame length polls
RX_POLL_MAX_ATTEMPTS = 50  # Max polls before timeout (5 seconds total)

# Pre-compiled struct operations for better performance
# Pack 4-byte big-endian unsigned integer
_PACK_UINT32_BE = struct.Struct(">I").pack
# Unpack 4-byte big-endian unsigned integer
_UNPACK_UINT32_BE = struct.Struct(">I").unpack


class BleRPC:
    """BLE RPC client for Shelly devices."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialize BLE RPC client.

        Args:
            ble_device: BLEDevice object from BleakScanner

        """
        self._ble_device = ble_device
        self._client: BleakClientWithServiceCache | None = None
        self._call_id = 0
        self._connected = False

    @property
    def _next_id(self) -> int:
        """Get next RPC call ID."""
        self._call_id += 1
        return self._call_id

    @property
    def connected(self) -> bool:
        """Return True if connected to device."""
        return (
            self._connected and self._client is not None and self._client.is_connected
        )

    async def connect(self) -> None:
        """Establish BLE connection to device."""
        if self.connected:
            raise RuntimeError("Already connected")

        address = self._ble_device.address
        _LOGGER.debug("Connecting to Shelly device at %s via BLE", address)

        # Retry once if characteristics are missing (cache issue)
        for attempt in range(MAX_CONNECTION_RETRIES):
            try:
                # Establish connection with retry support
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    self._ble_device,
                    address,
                    disconnected_callback=self._on_disconnect,
                )
            except (BleakError, TimeoutError, OSError) as err:
                raise BleConnectionError(
                    f"Failed to connect to {address}: {err}"
                ) from err

            # Verify RPC service and characteristics are available
            try:
                await self._verify_rpc_service()
            except BleCharacteristicNotFoundError as err:
                if attempt == 0:
                    # First attempt: clear cache and retry
                    _LOGGER.debug(
                        "%s: characteristic missing, clearing cache: %s",
                        address,
                        err,
                    )
                    await self._client.clear_cache()
                    await self._client.disconnect()
                    self._client = None
                    continue
                # Second attempt: give up
                await self._client.disconnect()
                self._client = None
                raise
            except (BleakError, OSError) as err:
                # Catch unexpected errors during service discovery
                await self._client.disconnect()
                self._client = None
                raise BleConnectionError(
                    f"Failed to verify RPC service on {address}: {err}"
                ) from err

            # Success
            break

        self._connected = True
        _LOGGER.info("Connected to Shelly device at %s via BLE", address)

    async def _verify_rpc_service(self) -> None:
        """Verify that the RPC service and characteristics are available."""
        self._raise_if_client_not_initialized()
        if TYPE_CHECKING:
            assert self._client is not None

        # Check for RPC service
        services = self._client.services
        rpc_service = services.get_service(RPC_SERVICE_UUID)
        if not rpc_service:
            raise BleCharacteristicNotFoundError(
                f"RPC service {RPC_SERVICE_UUID} not found"
            )

        # Check for required characteristics
        required_characteristics = {
            "Data": DATA_CHARACTERISTIC_UUID,
            "TX control": TX_CONTROL_CHARACTERISTIC_UUID,
            "RX control": RX_CONTROL_CHARACTERISTIC_UUID,
        }

        for name, uuid in required_characteristics.items():
            if not services.get_characteristic(uuid):
                raise BleCharacteristicNotFoundError(
                    f"{name} characteristic {uuid} not found"
                )

    def _on_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        """Handle BLE disconnection."""
        _LOGGER.info("Disconnected from Shelly device at %s", self._ble_device.address)
        self._connected = False

    def _raise_if_client_not_initialized(self) -> None:
        """Raise RuntimeError if client is not initialized."""
        if self._client is None:
            raise RuntimeError("Client not initialized")

    async def disconnect(self) -> None:
        """Disconnect from device."""
        if self._client is None:
            return

        _LOGGER.debug("Disconnecting from %s", self._ble_device.address)
        await self._client.disconnect()
        self._client = None
        self._connected = False

    def _validate_response_id(self, response: dict[str, Any], expected_id: int) -> None:
        """Validate response ID matches request ID."""
        if response.get("id") != expected_id:
            msg = (
                f"Response ID mismatch: expected {expected_id}, "
                f"got {response.get('id')}"
            )
            raise RpcCallError(0, msg)

    def _raise_for_response_error(self, response: dict[str, Any]) -> None:
        """Raise exception if response contains an error."""
        if "error" in response:
            error = response["error"]
            code = error.get("code", 0)
            message = error.get("message", "Unknown error")
            raise RpcCallError(code, message)

    def _extract_result(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract result from response or raise if invalid."""
        if "result" in response:
            result: dict[str, Any] = response["result"]
            return result
        # Response has neither error nor result
        raise RpcCallError(0, f"Invalid response: {response}")

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = DEVICE_IO_TIMEOUT,
    ) -> dict[str, Any]:
        """Execute RPC call over BLE.

        Args:
            method: RPC method name
            params: Optional parameters dict
            timeout: Request timeout in seconds

        Returns:
            RPC result dict

        Raises:
            DeviceConnectionError: If not connected
            DeviceConnectionTimeoutError: If request times out
            RpcCallError: If RPC returns an error

        """
        if not self.connected or self._client is None:
            raise DeviceConnectionError("Not connected to device")

        # Build RPC request
        call_id = self._next_id
        request = {
            "id": call_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        _LOGGER.debug("BLE RPC call: %s (id=%d)", method, call_id)

        # Send request and receive response
        try:
            request_data = json_bytes(request)
            await asyncio.wait_for(
                self._send_request(request_data),
                timeout=timeout,
            )

            response_data = await asyncio.wait_for(
                self._receive_response(),
                timeout=timeout,
            )
        except TimeoutError as err:
            raise DeviceConnectionTimeoutError(
                f"BLE RPC call timed out after {timeout}s"
            ) from err
        except (BleakError, OSError) as err:
            raise DeviceConnectionError(f"BLE RPC call failed: {err}") from err

        # Parse and validate response
        try:
            response: dict[str, Any] = json_loads(response_data)
        except ValueError as err:
            raise DeviceConnectionError(f"Invalid JSON in RPC response: {err}") from err

        self._validate_response_id(response, call_id)
        self._raise_for_response_error(response)
        return self._extract_result(response)

    async def _send_request(self, data: bytes) -> None:
        """Send RPC request over BLE.

        Protocol:
        1. Write request length (4-byte big-endian) to TX control characteristic
        2. Write request data to data characteristic

        Args:
            data: JSON-encoded request data

        """
        self._raise_if_client_not_initialized()
        if TYPE_CHECKING:
            assert self._client is not None

        # Write frame length to TX control characteristic using pre-compiled struct
        frame_length = _PACK_UINT32_BE(len(data))
        await self._client.write_gatt_char(TX_CONTROL_CHARACTERISTIC_UUID, frame_length)

        # Write data to data characteristic
        await self._client.write_gatt_char(DATA_CHARACTERISTIC_UUID, data)

        _LOGGER.debug("Sent %d bytes via BLE", len(data))

    async def _receive_response(self) -> bytes:
        """Receive RPC response over BLE.

        Protocol:
        1. Read frame length from RX control characteristic (4-byte big-endian)
        2. Read frame data from data characteristic

        Returns:
            JSON-encoded response data

        """
        self._raise_if_client_not_initialized()
        if TYPE_CHECKING:
            assert self._client is not None

        # Poll RX control characteristic for frame length
        # Frame length may be 0 while device prepares response
        frame_length = 0
        for _attempt in range(RX_POLL_MAX_ATTEMPTS):
            length_data = await self._client.read_gatt_char(
                RX_CONTROL_CHARACTERISTIC_UUID
            )
            if len(length_data) < UINT32_BYTES:
                msg = (
                    f"Invalid frame length data: expected {UINT32_BYTES} bytes, "
                    f"got {len(length_data)}"
                )
                raise DeviceConnectionError(msg)

            frame_length = _UNPACK_UINT32_BE(length_data[:UINT32_BYTES])[0]
            if frame_length == 0:
                # Device hasn't prepared response yet, wait and retry
                _LOGGER.debug("Frame length 0, polling again in %ss", RX_POLL_INTERVAL)
                await asyncio.sleep(RX_POLL_INTERVAL)
                continue

            # Got non-zero frame length
            break

        if frame_length == 0:
            timeout_s = RX_POLL_MAX_ATTEMPTS * RX_POLL_INTERVAL
            msg = (
                f"No response data available after {RX_POLL_MAX_ATTEMPTS} "
                f"poll attempts ({timeout_s}s)"
            )
            raise DeviceConnectionError(msg)

        _LOGGER.debug("Receiving %d bytes via BLE", frame_length)

        # Read data from data characteristic in chunks
        # Large responses may be split across multiple reads
        data_bytes = bytearray()
        chunk_num = 0
        while len(data_bytes) < frame_length:
            chunk = cast(
                bytes, await self._client.read_gatt_char(DATA_CHARACTERISTIC_UUID)
            )
            chunk_num += 1
            _LOGGER.debug(
                "Chunk %d: received %d bytes, total %d/%d",
                chunk_num,
                len(chunk),
                len(data_bytes) + len(chunk),
                frame_length,
            )
            if not chunk:
                # No more data available
                break
            data_bytes.extend(chunk)

        if len(data_bytes) < frame_length:
            msg = (
                f"Incomplete data received: expected {frame_length} bytes, "
                f"got {len(data_bytes)}"
            )
            raise DeviceConnectionError(msg)

        return bytes(data_bytes[:frame_length])
