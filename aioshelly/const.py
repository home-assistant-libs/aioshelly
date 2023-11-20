"""Constants for aioshelly."""
import asyncio

import aiohttp

from .exceptions import DeviceConnectionError

CONNECT_ERRORS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    DeviceConnectionError,
    OSError,
)

# Gen1 CoAP based models
MODEL_1 = "SHSW-1"
MODEL_1L = "SHSW-L"
MODEL_1PM = "SHSW-PM"
MODEL_2 = "SHSW-21"
MODEL_25 = "SHSW-25"
MODEL_2LED = "SH2LED-1"
MODEL_4PRO = "SHSW-44"  # CoAP v1, unsupported
MODEL_AIR = "SHAIR-1"
MODEL_BULB = "SHBLB-1"
MODEL_BULB_RGBW = "SHCB-1"
MODEL_BUTTON1 = "SHBTN-1"
MODEL_BUTTON1_V2 = "SHBTN-2"  # hw v2
MODEL_COLOR = "SHCL-255"
MODEL_DIMMER = "SHDM-1"
MODEL_DIMMER_2 = "SHDM-2"
MODEL_DIMMER_W1 = "SHDIMW-1"
MODEL_DUO = "SHBDUO-1"
MODEL_DW = "SHDW-1"
MODEL_DW_2 = "SHDW-2"
MODEL_EM = "SHEM"
MODEL_EM3 = "SHEM-3"
MODEL_FLOOD = "SHWT-1"
MODEL_GAS = "SHGS-1"
MODEL_HT = "SHHT-1"
MODEL_I3 = "SHIX3-1"
MODEL_MOTION = "SHMOS-01"
MODEL_MOTION_2 = "SHMOS-02"
MODEL_PLUG = "SHPLG-1"
MODEL_PLUG_E = "SHPLG2-1"
MODEL_PLUG_S = "SHPLG-S"
MODEL_PLUG_US = "SHPLG-U1"
MODEL_RGBW = "SHRGBWW-01"
MODEL_RGBW2 = "SHRGBW2"
MODEL_SENSE = "SHSEN-1"  # CoAP v1, unsupported
MODEL_SMOKE = "SHSM-01"
MODEL_SMOKE_2 = "SHSM-02"
MODEL_SPOT = "SHSPOT-1"
MODEL_SPOT_2 = "SHSPOT-2"
MODEL_UNI = "SHUNI-1"
MODEL_VALVE = "SHTRV-01"
MODEL_VINTAGE = "SHBVIN-1"
MODEL_VINTAGE_V2 = "SHVIN-1"


MODEL_NAMES = {
    # Gen1 CoAP based models
    MODEL_1: "Shelly 1",
    MODEL_1L: "Shelly 1L",
    MODEL_1PM: "Shelly 1PM",
    MODEL_2: "Shelly 2",
    MODEL_25: "Shelly 2.5",
    MODEL_2LED: "Shelly 2LED",
    MODEL_4PRO: "Shelly 4Pro",
    MODEL_AIR: "Shelly Air",
    MODEL_BULB: "Shelly Bulb",
    MODEL_BULB_RGBW: "Shelly Bulb RGBW",
    MODEL_BUTTON1: "Shelly Button1",
    MODEL_BUTTON1_V2: "Shelly Button1",
    MODEL_COLOR: "Shelly Color",
    MODEL_DIMMER: "Shelly Dimmer",
    MODEL_DIMMER_2: "Shelly Dimmer 2",
    MODEL_DIMMER_W1: "Shelly Dimmer W1",
    MODEL_DUO: "Shelly DUO",
    MODEL_DW: "Shelly Door/Window",
    MODEL_DW_2: "Shelly Door/Window 2",
    MODEL_EM: "Shelly EM",
    MODEL_EM3: "Shelly 3EM",
    MODEL_FLOOD: "Shelly Flood",
    MODEL_GAS: "Shelly Gas",
    MODEL_HT: "Shelly H&T",
    MODEL_I3: "Shelly i3",
    MODEL_MOTION: "Shelly Motion",
    MODEL_MOTION_2: "Shelly Motion 2",
    MODEL_PLUG: "Shelly Plug",
    MODEL_PLUG_E: "Shelly Plug E",
    MODEL_PLUG_S: "Shelly Plug S",
    MODEL_PLUG_US: "Shelly Plug US",
    MODEL_RGBW: "Shelly RGBW",
    MODEL_RGBW2: "Shelly RGBW2",
    MODEL_SENSE: "Shelly Sense",
    MODEL_SMOKE: "Shelly Smoke",
    MODEL_SMOKE_2: "Shelly Smoke 2",
    MODEL_SPOT: "Shelly Spot",
    MODEL_SPOT_2: "Shelly Spot 2",
    MODEL_UNI: "Shelly UNI",
    MODEL_VALVE: "Shelly Valve",
    MODEL_VINTAGE: "Shelly Vintage",
    MODEL_VINTAGE_V2: "Shelly Vintage",
    # Gen2 RPC based models
    "SAWD-0A1XX10EU1": "Shelly Wall Display",
    "SNGW-0A11WW010": "Shelly Plus 10V",
    "SNPL-00110IT": "Shelly Plus Plug IT",
    "SNPL-00112EU": "Shelly Plus Plug S",
    "SNPL-00112UK": "Shelly Plus Plug UK",
    "SNPL-00116US": "Shelly Plus Plug US",
    "SNPM-001PCEU16": "Shelly Plus PM Mini",
    "SNSN-0013A": "Shelly Plus H&T",
    "SNSN-0031Z": "Shelly Plus Smoke",
    "SNSN-0043X": "Shelly Plus Uni",
    "SNSN-0D24X": "Shelly Plus I4DC",
    "SNSW-001P15UL": "Shelly Plus 1PM UL",
    "SNSW-001P16EU": "Shelly Plus 1PM",
    "SNSW-001P8EU": "Shelly Plus 1PM Mini",
    "SNSW-001X15UL": "Shelly Plus 1 UL",
    "SNSW-001X16EU": "Shelly Plus 1",
    "SNSW-001X8EU": "Shelly Plus 1 Mini",
    "SNSW-0024X": "Shelly Plus I4",
    "SNSW-002P16EU": "Shelly Plus 2PM",
    "SNSW-102P16EU": "Shelly Plus 2PM",
    "SPEM-002CEBEU50": "Shelly Pro EM",
    "SPEM-003CEBEU": "Shelly Pro 3EM",
    "SPSH-002PE16EU": "Shelly Pro Dual Cover PM",
    "SPSW-001PE16EU": "Shelly Pro 1PM",
    "SPSW-001XE16EU": "Shelly Pro 1",
    "SPSW-002PE16EU": "Shelly Pro 2PM",
    "SPSW-002XE16EU": "Shelly Pro 2",
    "SPSW-003XE16EU": "Shelly Pro 3",
    "SPSW-004PE16EU": "Shelly Pro 4PM",
    "SPSW-101PE16EU": "Shelly Pro 1PM",
    "SPSW-101XE16EU": "Shelly Pro 1",
    "SPSW-102PE16EU": "Shelly Pro 2PM",
    "SPSW-102XE16EU": "Shelly Pro 2",
    "SPSW-104PE16EU": "Shelly Pro 4PM",
    "SPSW-201PE16EU": "Shelly Pro 1PM",
    "SPSW-201XE16EU": "Shelly Pro 1",
    "SPSW-202PE16EU": "Shelly Pro 2PM",
    "SPSW-202XE16EU": "Shelly Pro 2",
    "SNGW-BT01": "Shelly Blu Gateway",
}

# Timeout used for Device IO
DEVICE_IO_TIMEOUT = 10

# Timeout used for HTTP calls
HTTP_CALL_TIMEOUT = 10

# Firmware 1.8.0 release date (CoAP v2)
GEN1_MIN_FIRMWARE_DATE = 20200812

# Firmware 0.8.1 release date
GEN2_MIN_FIRMWARE_DATE = 20210921

WS_HEARTBEAT = 55

# Default Gen2 outbound websocket API URL
WS_API_URL = "/api/shelly/ws"

# Notification sent by RPC device in case of WebSocket close
NOTIFY_WS_CLOSED = "NotifyWebSocketClosed"
