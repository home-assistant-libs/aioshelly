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
# Gen2 RPC based models
MODEL_BLU_GATEWAY = "SNGW-BT01"
MODEL_PLUS_1 = "SNSW-001X16EU"
MODEL_PLUS_1_MINI = "SNSW-001X8EU"
MODEL_PLUS_1_UL = "SNSW-001X15UL"
MODEL_PLUS_10V = "SNGW-0A11WW010"  # pre-release of SNDM-00100WW
MODEL_PLUS_10V_DIMMER = "SNDM-00100WW"
MODEL_PLUS_1PM = "SNSW-001P16EU"
MODEL_PLUS_1PM_MINI = "SNSW-001P8EU"
MODEL_PLUS_1PM_UL = "SNSW-001P15UL"
MODEL_PLUS_2PM = "SNSW-002P16EU"
MODEL_PLUS_2PM_V2 = "SNSW-102P16EU"
MODEL_PLUS_HT = "SNSN-0013A"
MODEL_PLUS_I4 = "SNSW-0024X"
MODEL_PLUS_I4DC = "SNSN-0D24X"
MODEL_PLUS_PLUG_IT = "SNPL-00110IT"
MODEL_PLUS_PLUG_S = "SNPL-00112EU"
MODEL_PLUS_PLUG_UK = "SNPL-00112UK"
MODEL_PLUS_PLUG_US = "SNPL-00116US"
MODEL_PLUS_PM_MINI = "SNPM-001PCEU16"
MODEL_PLUS_SMOKE = "SNSN-0031Z"
MODEL_PLUS_UNI = "SNSN-0043X"
MODEL_PRO_1 = "SPSW-001XE16EU"
MODEL_PRO_1_V2 = "SPSW-101XE16EU"
MODEL_PRO_1_V3 = "SPSW-201XE16EU"
MODEL_PRO_1PM = "SPSW-001PE16EU"
MODEL_PRO_1PM_V2 = "SPSW-101PE16EU"
MODEL_PRO_1PM_V3 = "SPSW-201PE16EU"
MODEL_PRO_2 = "SPSW-002XE16EU"
MODEL_PRO_2_V2 = "SPSW-102XE16EU"
MODEL_PRO_2_V3 = "SPSW-202XE16EU"
MODEL_PRO_2PM = "SPSW-002PE16EU"
MODEL_PRO_2PM_V2 = "SPSW-102PE16EU"
MODEL_PRO_2PM_V2 = "SPSW-202PE16EU"
MODEL_PRO_3 = "SPSW-003XE16EU"
MODEL_PRO_4PM = "SPSW-004PE16EU"
MODEL_PRO_4PM_V2 = "SPSW-104PE16EU"
MODEL_PRO_DIMMER_1PM = "SPDM-001PE01EU"
MODEL_PRO_DIMMER_2PM = "SPDM-002PE01EU"
MODEL_PRO_DUAL_COVER = "SPSH-002PE16EU"
MODEL_PRO_EM = "SPEM-002CEBEU50"
MODEL_PRO_EM3 = "SPEM-003CEBEU"
MODEL_PRO_EM3_400 = "SPEM-003CEBEU400"
MODEL_WALL_DISPLAY = "SAWD-0A1XX10EU1"
# Gen3 RPC based models
MODEL_1_MINI_G3 = "S3SW-001X8EU"
MODEL_1PM_MINI_G3 = "S3SW-001P8EU"
MODEL_HT_G3 = "S3SN-0U12A"
MODEL_PM_MINI_G3 = "S3PM-001PCEU16"

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
    MODEL_BLU_GATEWAY: "Shelly BLU Gateway",
    MODEL_PLUS_1: "Shelly Plus 1",
    MODEL_PLUS_1_MINI: "Shelly Plus 1 Mini",
    MODEL_PLUS_1_UL: "Shelly Plus 1 UL",
    MODEL_PLUS_10V: "Shelly Plus 10V",
    MODEL_PLUS_10V_DIMMER: "Shelly Plus 0-10V Dimmer",
    MODEL_PLUS_1PM: "Shelly Plus 1PM",
    MODEL_PLUS_1PM_MINI: "Shelly Plus 1PM Mini",
    MODEL_PLUS_1PM_UL: "Shelly Plus 1PM UL",
    MODEL_PLUS_2PM: "Shelly Plus 2PM",
    MODEL_PLUS_2PM_V2: "Shelly Plus 2PM",
    MODEL_PLUS_HT: "Shelly Plus H&T",
    MODEL_PLUS_I4: "Shelly Plus I4",
    MODEL_PLUS_I4DC: "Shelly Plus I4DC",
    MODEL_PLUS_PLUG_IT: "Shelly Plus Plug IT",
    MODEL_PLUS_PLUG_S: "Shelly Plus Plug S",
    MODEL_PLUS_PLUG_UK: "Shelly Plus Plug UK",
    MODEL_PLUS_PLUG_US: "Shelly Plus Plug US",
    MODEL_PLUS_PM_MINI: "Shelly Plus PM Mini",
    MODEL_PLUS_SMOKE: "Shelly Plus Smoke",
    MODEL_PLUS_UNI: "Shelly Plus Uni",
    MODEL_PRO_1: "Shelly Pro 1",
    MODEL_PRO_1_V2: "Shelly Pro 1",
    MODEL_PRO_1_V3: "Shelly Pro 1",
    MODEL_PRO_1PM: "Shelly Pro 1PM",
    MODEL_PRO_1PM_V2: "Shelly Pro 1PM",
    MODEL_PRO_1PM_V3: "Shelly Pro 1PM",
    MODEL_PRO_2: "Shelly Pro 2",
    MODEL_PRO_2_V2: "Shelly Pro 2",
    MODEL_PRO_2_V3: "Shelly Pro 2",
    MODEL_PRO_2PM: "Shelly Pro 2PM",
    MODEL_PRO_2PM_V2: "Shelly Pro 2PM",
    MODEL_PRO_3: "Shelly Pro 3",
    MODEL_PRO_4PM: "Shelly Pro 4PM",
    MODEL_PRO_4PM_V2: "Shelly Pro 4PM",
    MODEL_PRO_DIMMER_1PM: "Shelly Pro Dimmer 1PM",
    MODEL_PRO_DIMMER_2PM: "Shelly Pro Dimmer 2PM",
    MODEL_PRO_DUAL_COVER: "Shelly Pro Dual Cover PM",
    MODEL_PRO_EM: "Shelly Pro EM",
    MODEL_PRO_EM3: "Shelly Pro 3EM",
    MODEL_PRO_EM3_400: "Shelly Pro 3EM-400",
    MODEL_WALL_DISPLAY: "Shelly Wall Display",
    # Gen3 RPC based models
    MODEL_1_MINI_G3: "Shelly 1 Mini Gen3",
    MODEL_1PM_MINI_G3: "Shelly 1PM Mini Gen3",
    MODEL_HT_G3: "Shelly H&T Gen3",
    MODEL_PM_MINI_G3: "Shelly PM Mini Gen3",
}

GEN1_MODELS_SUPPORTING_LIGHT_TRANSITION = (
    MODEL_DUO,
    MODEL_BULB_RGBW,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_RGBW2,
    MODEL_VINTAGE_V2,
)

# Timeout used for Device IO
DEVICE_IO_TIMEOUT = 10

# Timeout used for HTTP calls
HTTP_CALL_TIMEOUT = 10

# Firmware 1.9.0 release date
GEN1_MIN_FIRMWARE_DATE = 20201124

# Firmware 1.11.0 release date (introduction of light transition)
# Due to date fluctuation for different models, 20210710 was used.
GEN1_LIGHT_TRANSITION_MIN_FIRMWARE_DATE = 20210710

# Firmware 1.0.0 release date
GEN2_MIN_FIRMWARE_DATE = 20230803

# Firmware 1.0.99 release date
GEN3_MIN_FIRMWARE_DATE = 20231102

WS_HEARTBEAT = 55

# Default Gen2 outbound websocket API URL
WS_API_URL = "/api/shelly/ws"

# Notification sent by RPC device in case of WebSocket close
NOTIFY_WS_CLOSED = "NotifyWebSocketClosed"

BLOCK_GENERATIONS = (1,)
RPC_GENERATIONS = (2, 3)
