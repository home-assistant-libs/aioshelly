# Instructions for AI Agent

This file provides guidance to AI agent when working with code in this repository.

## What this is

`aioshelly` is the asyncio Python library Home Assistant uses to talk to Shelly devices. It is
published to PyPI from this repo (version is set at release time; `pyproject.toml` keeps `0.0.0`).
Home Assistant core is the primary consumer, so public API changes have downstream impact.

Contribution rule from the README: object hierarchy and property/method names must match the
[Shelly API](https://shelly-api-docs.shelly.cloud/). For example the RPC method `Switch.SetConfig`
is exposed as `RpcDevice.switch_setconfig`.

Official documentation for the devices and their APIs:

- Gen1 devices (Block/CoAP, `block_device/`): https://shelly-api-docs.shelly.cloud/gen1/#shelly-family-overview
- Gen2+ devices (RPC, `rpc_device/`): https://shelly-api-docs.shelly.cloud/gen2/
- BLU devices (Bluetooth, `ble/`): https://shelly-api-docs.shelly.cloud/docs-ble/

## Rules

- New code must be covered by tests. No exceptions: every new function, branch, and error path
  added in a change ships with tests in the same change.
- Comments explain why something is done, not what the code does. Do not restate the code or add
  comments for obvious decisions.

## Commands

Environment is managed with `uv` (`uv sync --all-groups`, then `uv run prek install` for hooks).
`script/environment.sh` does both. Always run tools through `uv run`.

```bash
uv run python -m pytest                                  # full test suite (~5 s)
uv run python -m pytest tests/rpc_device/test_device.py  # one file
uv run python -m pytest tests/rpc_device/test_device.py -k "test_name"   # one test
uv run python -m pytest --cov=aioshelly --cov-report=term-missing        # with coverage

uv run ruff format ./            # format (ruff config: lint.select = ALL, py312 target)
uv run ruff check ./ --fix       # lint
uv run pydocstyle aioshelly      # docstring checks (every public function/class needs one)
uv run ty check                  # type checking (only `aioshelly/` is included, not tests/tools)
uv run prek run --all-files      # all pre-commit hooks (pyupgrade, codespell, yamllint, ty, ...)
uv run tox                       # everything CI runs, across Python 3.12-3.15
```

Tests are pytest-asyncio with `asyncio_default_fixture_loop_scope = "function"`; async test
functions and fixtures need no marker beyond the `pytest_asyncio.fixture` decorator used in
the existing conftests.

Pre-commit blocks commits to `main` directly; work on a branch. PRs must carry one of the
labels checked by `.github/workflows/pr-labels.yml` (`bugfix`, `new-feature`, `enhancement`,
`breaking-change`, `refactor`, `maintenance`, `dependencies`, ...); release-drafter uses the
label to pick the semver bump.

Example/debug scripts live in `tools/` and import a sibling `common` package, so invoke them
by path (`python3 tools/example.py -ip <ip> -i`, `-h` for options). `tools/fixture.py` records
real-device responses into the top-level `fixtures/` directory.

## Architecture

The package is split by Shelly device generation, with a thin shared layer:

```
aioshelly/
  common.py        ConnectionOptions, get_info() (GET /shelly), firmware support check
  const.py         MODEL_* ids, DEVICES registry (ShellyDevice: name, gen, min_fw_date,
                   supported, BLE model_id), timeouts, GEN constants
  exceptions.py    ShellyError hierarchy (see below)
  json.py          orjson wrappers (json_loads / json_dumps / json_bytes); always use these
  block_device/    Gen1: HTTP REST + CoAP (CoIoT) push
  rpc_device/      Gen2/3/4: JSON-RPC over WebSocket or BLE
  ble/             Gen2+ as Bluetooth proxy, BLE advertisement parsing, WiFi provisioning
  zeroconf.py      mDNS discovery helpers
```

### Gen1 — `block_device/`

- `COAP` (`coap.py`) is an `asyncio.DatagramProtocol` bound to the multicast CoIoT port. One
  instance is shared across devices; `BlockDevice` subscribes by IP and gets `CoapMessage`
  callbacks. CoIoT is UDP multicast, which is why Gen1 refuses custom ports
  (`CustomPortNotSupported`).
- `BlockDevice.initialize()` fetches `/shelly`, `/settings`, `/status` over HTTP, then requests
  `cit/d` (device description: blocks and sensors) and `cit/s` (current sensor values) over CoAP.
- `Block` objects are built from `cit/d`. `Block.__getattr__` resolves sensor descriptions to
  values from the last `cit/s` payload, and `Block.TYPES` is a registry populated by
  `__init_subclass__(blk_type=...)` (e.g. `LightBlock`). Commands go out as HTTP GETs via
  `set_state(**kwargs)`.
- Listeners receive `BlockUpdateType` (`COAP_PERIODIC`, `COAP_REPLY`, `INITIALIZED`, `ONLINE`).

### Gen2+ — `rpc_device/`

- `RpcDevice` is transport-agnostic. It holds either a `WsRPC` (IP given) or a `BleRPC`
  (`ConnectionOptions.ble_device` given); `ConnectionOptions.__post_init__` enforces exactly one.
  Only `WsRPC` supports batched calls and digest auth; `BleRPC` runs calls sequentially.
- Initialization order matters (`_init_calls`): `Shelly.GetDeviceInfo` is the only unauthenticated
  call and yields the auth realm, then `Shelly.GetConfig`, `Shelly.GetStatus` and, if the firmware
  supports it, paginated `Shelly.GetComponents(dynamic_only=True)` for virtual components and
  BLU TRVs. Dynamic components are merged into `config`/`status` under keys like `number:200`
  or `blutrv:200`.
- `status`, `config`, `shelly` properties raise `NotInitialized` until loaded and keep the last
  known values across re-initialization.
- Push updates: `WsRPC` receives `NotifyStatus` (deep-merged via `mergedicts`),
  `NotifyFullStatus` and `NotifyEvent` and forwards them as `RpcUpdateType` to the single
  listener set with `subscribe_updates()`. `RPCSource` distinguishes frames from the outbound
  connection (`CLIENT`) from frames the device pushed to us (`SERVER`).
- `WsServer` is the inbound WebSocket server (default path `/api/shelly/ws`). Battery-powered
  devices connect to it when they wake; frames are routed to the subscribed `RpcDevice` by
  device MAC (parsed from the `src` field) or by IP. The `ONLINE` update type signals a
  sleeping device that woke up before initialization.
- `models.py` holds `TypedDict`s for RPC results (`ShellySwitchConfig`, `ShellyWsConfig`, ...).
  New typed wrappers follow the pattern `cast(ShellyXConfig, await self.call_rpc("X.GetConfig", ...))`.
- `update_component_config(key)` derives the RPC namespace from the component key by
  capitalizing it; namespaces that do not follow that rule go in
  `RPC_CONFIG_NAMESPACE_OVERRIDES`.
- `BleRPC` (`blerpc.py`) implements the RPC-over-GATT framing: 4-byte big-endian length written
  to the TX control characteristic, payload on the data characteristic, polled RX length.

### BLE — `ble/`

- Shelly Gen2+ devices act as Bluetooth proxies by running a JS script (`BLE_CODE` in
  `ble/const.py`, installed under the name `aioshelly_ble_integration`). `async_start_scanner`
  uploads the script only when its code differs, to avoid flash writes, and toggles active
  scanning through `Script.Eval` rather than rewriting the script.
- `ShellyBLEScanner` (`ble/backend/scanner.py`) extends habluetooth's `BaseHaRemoteScanner`,
  consumes `ble.scan_result` events (parsed by `ble/parser.py`, versioned payload) and feeds
  raw advertisements into Home Assistant's Bluetooth stack.
- `ble/manufacturer_data.py` parses Allterco manufacturer data (flags, MAC, model id) from
  advertisements; `MODEL_ID_TO_DEVICE` in `const.py` maps model ids back to `ShellyDevice`.
- `ble/provisioning.py` provides WiFi provisioning for unconfigured devices over `BleRPC`.

### Errors and firmware gating

`exceptions.py` separates internal errors (`NotInitialized`, `WrongShellyGen`,
`ConnectionClosed`, `InvalidMessage`) from caller-facing ones (`DeviceConnectionError` and
its subclasses, `InvalidAuthError`, `RpcCallError` with `code`/`message`,
`MacAddressMismatchError`). Device classes catch `CONNECT_ERRORS` (`aiohttp.ClientError`,
`DeviceConnectionError`, `OSError`), wrap them, store the result in `last_error`, and re-raise.

Firmware support is decided by release date, not version string: `FIRMWARE_PATTERN` extracts
the leading `YYYYMMDD` and compares it with `ShellyDevice.min_fw_date` (or the per-generation
fallback in `MIN_FIRMWARE_DATES`). Feature gates such as `VIRTUAL_COMPONENTS_MIN_FIRMWARE`
use the same scheme. Adding a device means adding a `MODEL_*` constant and a `DEVICES` entry.

### Tests

Tests mirror the package layout. `tests/rpc_device/conftest.py` provides `WsRPCMocker`, which
queues canned JSON-RPC responses and rewrites their ids, plus an `rpc_device` fixture whose
`call_rpc_multiple` is an `AsyncMock`. Real device responses live in
`tests/rpc_device/fixtures/<device>/<Rpc.Method>` and are loaded with `load_device_fixture()`.
BLE tests auto-start a `habluetooth.BluetoothManager` via an autouse fixture.
