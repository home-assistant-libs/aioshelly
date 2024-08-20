"""Constants for aioshelly."""

import asyncio
import re

import aiohttp

from .exceptions import DeviceConnectionError

CONNECT_ERRORS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    DeviceConnectionError,
    OSError,
)

ATTR_MIN_FW_DATE = "min_fw_date"
ATTR_MODEL_NAME = "model_name"

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
MODEL_PLUS_2PM_UL = "SNSW-002P15UL"
MODEL_PLUS_2PM_V2 = "SNSW-102P16EU"
MODEL_PLUS_HT = "SNSN-0013A"
MODEL_PLUS_I4 = "SNSN-0024X"
MODEL_PLUS_I4DC = "SNSN-0D24X"
MODEL_PLUS_PLUG_IT = "SNPL-00110IT"
MODEL_PLUS_PLUG_S = "SNPL-00112EU"
MODEL_PLUS_PLUG_S_V2 = "SNPL-10112EU"  # hw v2
MODEL_PLUS_PLUG_UK = "SNPL-00112UK"
MODEL_PLUS_PLUG_US = "SNPL-00116US"
MODEL_PLUS_PM_MINI = "SNPM-001PCEU16"
MODEL_PLUS_RGBW_PM = "SNDC-0D4P10WW"
MODEL_PLUS_SMOKE = "SNSN-0031Z"
MODEL_PLUS_UNI = "SNSN-0043X"
MODEL_PLUS_WALL_DIMMER = "SNDM-0013US"
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
MODEL_PRO_EM3_120 = "SPEM-003CEBEU120"
MODEL_PRO_EM3_400 = "SPEM-003CEBEU400"
MODEL_WALL_DISPLAY = "SAWD-0A1XX10EU1"
# Gen3 RPC based models
MODEL_1_GEN3 = "S3SW-001X16EU"
MODEL_1_MINI_G3 = "S3SW-001X8EU"
MODEL_1PM_GEN3 = "S3SW-001P16EU"
MODEL_1PM_MINI_G3 = "S3SW-001P8EU"
MODEL_2PM_G3 = "S3SW-002P16EU"
MODEL_DIMMER_10V_GEN3 = "S3DM-0010WW"
MODEL_HT_G3 = "S3SN-0U12A"
MODEL_I4_GEN3 = "S3SN-0024X"
MODEL_PM_MINI_G3 = "S3PM-001PCEU16"
MODEL_X_MOD1 = "S3MX-0A"

DEVICES = {
    # Gen1 CoAP based models
    MODEL_1: {ATTR_MODEL_NAME: "Shelly 1", ATTR_MIN_FW_DATE: 20201124},
    MODEL_1L: {ATTR_MODEL_NAME: "Shelly 1L", ATTR_MIN_FW_DATE: 20201124},
    MODEL_1PM: {ATTR_MODEL_NAME: "Shelly 1PM", ATTR_MIN_FW_DATE: 20201124},
    MODEL_2: {ATTR_MODEL_NAME: "Shelly 2", ATTR_MIN_FW_DATE: 20201124},
    MODEL_25: {ATTR_MODEL_NAME: "Shelly 2.5", ATTR_MIN_FW_DATE: 20201124},
    MODEL_2LED: {ATTR_MODEL_NAME: "Shelly 2LED", ATTR_MIN_FW_DATE: 20201124},
    MODEL_4PRO: {ATTR_MODEL_NAME: "Shelly 4Pro", ATTR_MIN_FW_DATE: 20201124},
    MODEL_AIR: {ATTR_MODEL_NAME: "Shelly Air", ATTR_MIN_FW_DATE: 20201124},
    MODEL_BULB: {ATTR_MODEL_NAME: "Shelly Bulb", ATTR_MIN_FW_DATE: 20201124},
    MODEL_BULB_RGBW: {ATTR_MODEL_NAME: "Shelly Bulb RGBW", ATTR_MIN_FW_DATE: 20210710},
    MODEL_BUTTON1: {ATTR_MODEL_NAME: "Shelly Button1", ATTR_MIN_FW_DATE: 20201124},
    MODEL_BUTTON1_V2: {ATTR_MODEL_NAME: "Shelly Button1", ATTR_MIN_FW_DATE: 20201124},
    MODEL_COLOR: {ATTR_MODEL_NAME: "Shelly Color", ATTR_MIN_FW_DATE: 20201124},
    MODEL_DIMMER: {ATTR_MODEL_NAME: "Shelly Dimmer", ATTR_MIN_FW_DATE: 20210710},
    MODEL_DIMMER_2: {ATTR_MODEL_NAME: "Shelly Dimmer 2", ATTR_MIN_FW_DATE: 20210710},
    MODEL_DIMMER_W1: {ATTR_MODEL_NAME: "Shelly Dimmer W1", ATTR_MIN_FW_DATE: 20201124},
    MODEL_DUO: {ATTR_MODEL_NAME: "Shelly DUO", ATTR_MIN_FW_DATE: 20210710},
    MODEL_DW: {ATTR_MODEL_NAME: "Shelly Door/Window", ATTR_MIN_FW_DATE: 20201124},
    MODEL_DW_2: {ATTR_MODEL_NAME: "Shelly Door/Window 2", ATTR_MIN_FW_DATE: 20201124},
    MODEL_EM: {ATTR_MODEL_NAME: "Shelly EM", ATTR_MIN_FW_DATE: 20201124},
    MODEL_EM3: {ATTR_MODEL_NAME: "Shelly 3EM", ATTR_MIN_FW_DATE: 20201124},
    MODEL_FLOOD: {ATTR_MODEL_NAME: "Shelly Flood", ATTR_MIN_FW_DATE: 20201124},
    MODEL_GAS: {ATTR_MODEL_NAME: "Shelly Gas", ATTR_MIN_FW_DATE: 20201124},
    MODEL_HT: {ATTR_MODEL_NAME: "Shelly H&T", ATTR_MIN_FW_DATE: 20201124},
    MODEL_I3: {ATTR_MODEL_NAME: "Shelly i3", ATTR_MIN_FW_DATE: 20201124},
    MODEL_MOTION: {ATTR_MODEL_NAME: "Shelly Motion", ATTR_MIN_FW_DATE: 20201124},
    MODEL_MOTION_2: {ATTR_MODEL_NAME: "Shelly Motion 2", ATTR_MIN_FW_DATE: 20201124},
    MODEL_PLUG: {ATTR_MODEL_NAME: "Shelly Plug", ATTR_MIN_FW_DATE: 20201124},
    MODEL_PLUG_E: {ATTR_MODEL_NAME: "Shelly Plug E", ATTR_MIN_FW_DATE: 20201124},
    MODEL_PLUG_S: {ATTR_MODEL_NAME: "Shelly Plug S", ATTR_MIN_FW_DATE: 20201124},
    MODEL_PLUG_US: {ATTR_MODEL_NAME: "Shelly Plug US", ATTR_MIN_FW_DATE: 20201124},
    MODEL_RGBW: {ATTR_MODEL_NAME: "Shelly RGBW", ATTR_MIN_FW_DATE: 20201124},
    MODEL_RGBW2: {ATTR_MODEL_NAME: "Shelly RGBW2", ATTR_MIN_FW_DATE: 20210710},
    MODEL_SENSE: {ATTR_MODEL_NAME: "Shelly Sense", ATTR_MIN_FW_DATE: 20201124},
    MODEL_SMOKE: {ATTR_MODEL_NAME: "Shelly Smoke", ATTR_MIN_FW_DATE: 20201124},
    MODEL_SMOKE_2: {ATTR_MODEL_NAME: "Shelly Smoke 2", ATTR_MIN_FW_DATE: 20201124},
    MODEL_SPOT: {ATTR_MODEL_NAME: "Shelly Spot", ATTR_MIN_FW_DATE: 20201124},
    MODEL_SPOT_2: {ATTR_MODEL_NAME: "Shelly Spot 2", ATTR_MIN_FW_DATE: 20201124},
    MODEL_UNI: {ATTR_MODEL_NAME: "Shelly UNI", ATTR_MIN_FW_DATE: 20201124},
    MODEL_VALVE: {ATTR_MODEL_NAME: "Shelly Valve", ATTR_MIN_FW_DATE: 20201124},
    MODEL_VINTAGE: {ATTR_MODEL_NAME: "Shelly Vintage", ATTR_MIN_FW_DATE: 20201124},
    MODEL_VINTAGE_V2: {ATTR_MODEL_NAME: "Shelly Vintage", ATTR_MIN_FW_DATE: 20210710},
    # Gen2 RPC based models
    MODEL_BLU_GATEWAY: {
        ATTR_MODEL_NAME: "Shelly BLU Gateway",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_1: {ATTR_MODEL_NAME: "Shelly Plus 1", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_1_MINI: {
        ATTR_MODEL_NAME: "Shelly Plus 1 Mini",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_1_UL: {ATTR_MODEL_NAME: "Shelly Plus 1 UL", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_10V: {ATTR_MODEL_NAME: "Shelly Plus 10V", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_10V_DIMMER: {
        ATTR_MODEL_NAME: "Shelly Plus 0-10V Dimmer",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_1PM: {ATTR_MODEL_NAME: "Shelly Plus 1PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_1PM_MINI: {
        ATTR_MODEL_NAME: "Shelly Plus 1PM Mini",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_1PM_UL: {
        ATTR_MODEL_NAME: "Shelly Plus 1PM UL",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_2PM: {ATTR_MODEL_NAME: "Shelly Plus 2PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_2PM_UL: {
        ATTR_MODEL_NAME: "Shelly Plus 2PM UL",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_2PM_V2: {ATTR_MODEL_NAME: "Shelly Plus 2PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_HT: {ATTR_MODEL_NAME: "Shelly Plus H&T", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_I4: {ATTR_MODEL_NAME: "Shelly Plus I4", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_I4DC: {ATTR_MODEL_NAME: "Shelly Plus I4DC", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_PLUG_IT: {
        ATTR_MODEL_NAME: "Shelly Plus Plug IT",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_PLUG_S: {
        ATTR_MODEL_NAME: "Shelly Plus Plug S",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_PLUG_S_V2: {
        ATTR_MODEL_NAME: "Shelly Plus Plug S",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_PLUG_UK: {
        ATTR_MODEL_NAME: "Shelly Plus Plug UK",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_PLUG_US: {
        ATTR_MODEL_NAME: "Shelly Plus Plug US",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_PM_MINI: {
        ATTR_MODEL_NAME: "Shelly Plus PM Mini",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_RGBW_PM: {
        ATTR_MODEL_NAME: "Shelly Plus RGBW PM",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_SMOKE: {
        ATTR_MODEL_NAME: "Shelly Plus Smoke",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PLUS_UNI: {ATTR_MODEL_NAME: "Shelly Plus Uni", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PLUS_WALL_DIMMER: {
        ATTR_MODEL_NAME: "Shelly Plus Wall Dimmer",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PRO_1: {ATTR_MODEL_NAME: "Shelly Pro 1", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_1_V2: {ATTR_MODEL_NAME: "Shelly Pro 1", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_1_V3: {ATTR_MODEL_NAME: "Shelly Pro 1", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_1PM: {ATTR_MODEL_NAME: "Shelly Pro 1PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_1PM_V2: {ATTR_MODEL_NAME: "Shelly Pro 1PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_1PM_V3: {ATTR_MODEL_NAME: "Shelly Pro 1PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_2: {ATTR_MODEL_NAME: "Shelly Pro 2", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_2_V2: {ATTR_MODEL_NAME: "Shelly Pro 2", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_2_V3: {ATTR_MODEL_NAME: "Shelly Pro 2", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_2PM: {ATTR_MODEL_NAME: "Shelly Pro 2PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_2PM_V2: {ATTR_MODEL_NAME: "Shelly Pro 2PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_3: {ATTR_MODEL_NAME: "Shelly Pro 3", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_4PM: {ATTR_MODEL_NAME: "Shelly Pro 4PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_4PM_V2: {ATTR_MODEL_NAME: "Shelly Pro 4PM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_DIMMER_1PM: {
        ATTR_MODEL_NAME: "Shelly Pro Dimmer 1PM",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PRO_DIMMER_2PM: {
        ATTR_MODEL_NAME: "Shelly Pro Dimmer 2PM",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PRO_DUAL_COVER: {
        ATTR_MODEL_NAME: "Shelly Pro Dual Cover PM",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_PRO_EM: {ATTR_MODEL_NAME: "Shelly Pro EM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_EM3: {ATTR_MODEL_NAME: "Shelly Pro 3EM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_EM3_120: {ATTR_MODEL_NAME: "Shelly Pro 3EM", ATTR_MIN_FW_DATE: 20230803},
    MODEL_PRO_EM3_400: {
        ATTR_MODEL_NAME: "Shelly Pro 3EM-400",
        ATTR_MIN_FW_DATE: 20230803,
    },
    MODEL_WALL_DISPLAY: {
        ATTR_MODEL_NAME: "Shelly Wall Display",
        ATTR_MIN_FW_DATE: 20230803,
    },
    # Gen3 RPC based models
    MODEL_1_GEN3: {ATTR_MODEL_NAME: "Shelly 1 Gen3", ATTR_MIN_FW_DATE: 20231102},
    MODEL_1_MINI_G3: {
        ATTR_MODEL_NAME: "Shelly 1 Mini Gen3",
        ATTR_MIN_FW_DATE: 20231102,
    },
    MODEL_1PM_GEN3: {ATTR_MODEL_NAME: "Shelly 1PM Gen3", ATTR_MIN_FW_DATE: 20231102},
    MODEL_1PM_MINI_G3: {
        ATTR_MODEL_NAME: "Shelly 1PM Mini Gen3",
        ATTR_MIN_FW_DATE: 20231102,
    },
    MODEL_2PM_G3: {ATTR_MODEL_NAME: "Shelly 2PM Gen3", ATTR_MIN_FW_DATE: 20231102},
    MODEL_DIMMER_10V_GEN3: {
        ATTR_MODEL_NAME: "Shelly Dimmer 0/1-10V PM Gen3",
        ATTR_MIN_FW_DATE: 20231102,
    },
    MODEL_HT_G3: {ATTR_MODEL_NAME: "Shelly H&T Gen3", ATTR_MIN_FW_DATE: 20231102},
    MODEL_I4_GEN3: {ATTR_MODEL_NAME: "Shelly I4 Gen3", ATTR_MIN_FW_DATE: 20231102},
    MODEL_PM_MINI_G3: {
        ATTR_MODEL_NAME: "Shelly PM Mini Gen3",
        ATTR_MIN_FW_DATE: 20231102,
    },
    MODEL_X_MOD1: {ATTR_MODEL_NAME: "Shelly X MOD1", ATTR_MIN_FW_DATE: 20231102},
}

GEN1_MODELS_SUPPORTING_LIGHT_TRANSITION = (
    MODEL_DUO,
    MODEL_BULB_RGBW,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_RGBW2,
    MODEL_VINTAGE_V2,
)

GEN1_MODELS_UNSUPPORTED = (
    MODEL_4PRO,
    MODEL_SENSE,
)

# Timeout used for Device IO
DEVICE_IO_TIMEOUT = 10

# Timeout used for HTTP calls
HTTP_CALL_TIMEOUT = 10

WS_HEARTBEAT = 55

# Default network settings for gen1 devices ( CoAP )
DEFAULT_COAP_PORT = 5683

# Default Gen2 outbound websocket API URL
WS_API_URL = "/api/shelly/ws"

# Notification sent by RPC device in case of WebSocket close
NOTIFY_WS_CLOSED = "NotifyWebSocketClosed"

GEN1 = 1
GEN2 = 2
GEN3 = 3

MIN_FIRMWARE_DATES = {
    GEN1: 20201124,  # Firmware 1.9.0 release date
    GEN2: 20230803,  # Firmware 1.0.0 release date
    GEN3: 20231102,  # Firmware 1.0.99 release date
}

BLOCK_GENERATIONS = (GEN1,)
RPC_GENERATIONS = (GEN2, GEN3)

DEFAULT_HTTP_PORT = 80
PERIODIC_COAP_TYPE_CODE = 30
END_OF_OPTIONS_MARKER = 0xFF

FIRMWARE_PATTERN = re.compile(r"^(\d{8})")

VIRTUAL_COMPONENTS = ("boolean", "button", "enum", "number", "text")
# Firmware 1.2.0 release date
VIRTUAL_COMPONENTS_MIN_FIRMWARE = 20240213
