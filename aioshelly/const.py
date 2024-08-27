"""Constants for aioshelly."""

import asyncio
import re
from dataclasses import dataclass

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


GEN1 = 1
GEN2 = 2
GEN3 = 3


GEN1_MIN_FIRMWARE_DATE = 20201124  # Firmware 1.9.0 release date
GEN2_MIN_FIRMWARE_DATE = 20230803  # Firmware 1.0.0 release date
GEN3_MIN_FIRMWARE_DATE = 20231102  # Firmware 1.0.99 release date

# Fallback for unknown devices
MIN_FIRMWARE_DATES = {
    GEN1: GEN1_MIN_FIRMWARE_DATE,
    GEN2: GEN2_MIN_FIRMWARE_DATE,
    GEN3: GEN3_MIN_FIRMWARE_DATE,
}


@dataclass(frozen=True, slots=True)
class ShellyDevice:
    """Shelly device."""

    model: str
    name: str
    min_fw_date: int
    gen: int
    supported: bool
    gen1_light_transition: bool


DEVICES = {
    "SHSW-1": ShellyDevice(
        model="SHSW-1",
        name="Shelly 1",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSW-L": ShellyDevice(
        model="SHSW-L",
        name="Shelly 1L",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSW-PM": ShellyDevice(
        model="SHSW-PM",
        name="Shelly 1PM",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSW-21": ShellyDevice(
        model="SHSW-21",
        name="Shelly 2",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSW-25": ShellyDevice(
        model="SHSW-25",
        name="Shelly 2.5",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SH2LED-1": ShellyDevice(
        model="SH2LED-1",
        name="Shelly 2LED",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSW-44": ShellyDevice(
        model="SHSW-44",
        name="Shelly 4Pro",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=False,
        gen1_light_transition=False,
    ),
    "SHAIR-1": ShellyDevice(
        model="SHAIR-1",
        name="Shelly Air",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHBLB-1": ShellyDevice(
        model="SHBLB-1",
        name="Shelly Bulb",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHCB-1": ShellyDevice(
        model="SHCB-1",
        name="Shelly Bulb RGBW",
        min_fw_date=20210710,
        gen=GEN1,
        supported=True,
        gen1_light_transition=True,
    ),
    "SHBTN-1": ShellyDevice(
        model="SHBTN-1",
        name="Shelly Button1",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHBTN-2": ShellyDevice(
        model="SHBTN-2",
        name="Shelly Button1",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHCL-255": ShellyDevice(
        model="SHCL-255",
        name="Shelly Color",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHDM-1": ShellyDevice(
        model="SHDM-1",
        name="Shelly Dimmer",
        min_fw_date=20210710,
        gen=GEN1,
        supported=True,
        gen1_light_transition=True,
    ),
    "SHDM-2": ShellyDevice(
        model="SHDM-2",
        name="Shelly Dimmer 2",
        min_fw_date=20210710,
        gen=GEN1,
        supported=True,
        gen1_light_transition=True,
    ),
    "SHDIMW-1": ShellyDevice(
        model="SHDIMW-1",
        name="Shelly Dimmer W1",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHBDUO-1": ShellyDevice(
        model="SHBDUO-1",
        name="Shelly DUO",
        min_fw_date=20210710,
        gen=GEN1,
        supported=True,
        gen1_light_transition=True,
    ),
    "SHDW-1": ShellyDevice(
        model="SHDW-1",
        name="Shelly Door/Window",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHDW-2": ShellyDevice(
        model="SHDW-2",
        name="Shelly Door/Window 2",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHEM": ShellyDevice(
        model="SHEM",
        name="Shelly EM",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHEM-3": ShellyDevice(
        model="SHEM-3",
        name="Shelly 3EM",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHWT-1": ShellyDevice(
        model="SHWT-1",
        name="Shelly Flood",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHGS-1": ShellyDevice(
        model="SHGS-1",
        name="Shelly Gas",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHHT-1": ShellyDevice(
        model="SHHT-1",
        name="Shelly H&T",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHIX3-1": ShellyDevice(
        model="SHIX3-1",
        name="Shelly i3",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHMOS-01": ShellyDevice(
        model="SHMOS-01",
        name="Shelly Motion",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHMOS-02": ShellyDevice(
        model="SHMOS-02",
        name="Shelly Motion 2",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHPLG-1": ShellyDevice(
        model="SHPLG-1",
        name="Shelly Plug",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHPLG2-1": ShellyDevice(
        model="SHPLG2-1",
        name="Shelly Plug E",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHPLG-S": ShellyDevice(
        model="SHPLG-S",
        name="Shelly Plug S",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHPLG-U1": ShellyDevice(
        model="SHPLG-U1",
        name="Shelly Plug US",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHRGBWW-01": ShellyDevice(
        model="SHRGBWW-01",
        name="Shelly RGBW",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHRGBW2": ShellyDevice(
        model="SHRGBW2",
        name="Shelly RGBW2",
        min_fw_date=20210710,
        gen=GEN1,
        supported=True,
        gen1_light_transition=True,
    ),
    "SHSEN-1": ShellyDevice(
        model="SHSEN-1",
        name="Shelly Sense",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=False,
        gen1_light_transition=False,
    ),
    "SHSM-01": ShellyDevice(
        model="SHSM-01",
        name="Shelly Smoke",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSM-02": ShellyDevice(
        model="SHSM-02",
        name="Shelly Smoke 2",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSPOT-1": ShellyDevice(
        model="SHSPOT-1",
        name="Shelly Spot",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHSPOT-2": ShellyDevice(
        model="SHSPOT-2",
        name="Shelly Spot 2",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHUNI-1": ShellyDevice(
        model="SHUNI-1",
        name="Shelly UNI",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHTRV-01": ShellyDevice(
        model="SHTRV-01",
        name="Shelly Valve",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHBVIN-1": ShellyDevice(
        model="SHBVIN-1",
        name="Shelly Vintage",
        min_fw_date=GEN1_MIN_FIRMWARE_DATE,
        gen=GEN1,
        supported=True,
        gen1_light_transition=False,
    ),
    "SHVIN-1": ShellyDevice(
        model="SHVIN-1",
        name="Shelly Vintage",
        min_fw_date=20210710,
        gen=GEN1,
        supported=True,
        gen1_light_transition=True,
    ),
    "SNGW-BT01": ShellyDevice(
        model="SNGW-BT01",
        name="Shelly BLU Gateway",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-001X16EU": ShellyDevice(
        model="SNSW-001X16EU",
        name="Shelly Plus 1",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-001X8EU": ShellyDevice(
        model="SNSW-001X8EU",
        name="Shelly Plus 1 Mini",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-001X15UL": ShellyDevice(
        model="SNSW-001X15UL",
        name="Shelly Plus 1 UL",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNGW-0A11WW010": ShellyDevice(
        model="SNGW-0A11WW010",
        name="Shelly Plus 10V",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNDM-00100WW": ShellyDevice(
        model="SNDM-00100WW",
        name="Shelly Plus 0-10V Dimmer",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=0,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-001P16EU": ShellyDevice(
        model="SNSW-001P16EU",
        name="Shelly Plus 1PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-001P8EU": ShellyDevice(
        model="SNSW-001P8EU",
        name="Shelly Plus 1PM Mini",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-001P15UL": ShellyDevice(
        model="SNSW-001P15UL",
        name="Shelly Plus 1PM UL",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-002P16EU": ShellyDevice(
        model="SNSW-002P16EU",
        name="Shelly Plus 2PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=0,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-002P15UL": ShellyDevice(
        model="SNSW-002P15UL",
        name="Shelly Plus 2PM UL",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSW-102P16EU": ShellyDevice(
        model="SNSW-102P16EU",
        name="Shelly Plus 2PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSN-0013A": ShellyDevice(
        model="SNSN-0013A",
        name="Shelly Plus H&T",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSN-0024X": ShellyDevice(
        model="SNSN-0024X",
        name="Shelly Plus I4",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSN-0D24X": ShellyDevice(
        model="SNSN-0D24X",
        name="Shelly Plus I4DC",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNPL-00110IT": ShellyDevice(
        model="SNPL-00110IT",
        name="Shelly Plus Plug IT",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNPL-00112EU": ShellyDevice(
        model="SNPL-00112EU",
        name="Shelly Plus Plug S",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNPL-10112EU": ShellyDevice(
        model="SNPL-10112EU",
        name="Shelly Plus Plug S",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNPL-00112UK": ShellyDevice(
        model="SNPL-00112UK",
        name="Shelly Plus Plug UK",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNPL-00116US": ShellyDevice(
        model="SNPL-00116US",
        name="Shelly Plus Plug US",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=0,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNPM-001PCEU16": ShellyDevice(
        model="SNPM-001PCEU16",
        name="Shelly Plus PM Mini",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNDC-0D4P10WW": ShellyDevice(
        model="SNDC-0D4P10WW",
        name="Shelly Plus RGBW PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=0,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSN-0031Z": ShellyDevice(
        model="SNSN-0031Z",
        name="Shelly Plus Smoke",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNSN-0043X": ShellyDevice(
        model="SNSN-0043X",
        name="Shelly Plus Uni",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SNDM-0013US": ShellyDevice(
        model="SNDM-0013US",
        name="Shelly Plus Wall Dimmer",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-001XE16EU": ShellyDevice(
        model="SPSW-001XE16EU",
        name="Shelly Pro 1",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-101XE16EU": ShellyDevice(
        model="SPSW-101XE16EU",
        name="Shelly Pro 1",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-201XE16EU": ShellyDevice(
        model="SPSW-201XE16EU",
        name="Shelly Pro 1",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-001PE16EU": ShellyDevice(
        model="SPSW-001PE16EU",
        name="Shelly Pro 1PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-101PE16EU": ShellyDevice(
        model="SPSW-101PE16EU",
        name="Shelly Pro 1PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-201PE16EU": ShellyDevice(
        model="SPSW-201PE16EU",
        name="Shelly Pro 1PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=0,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-002XE16EU": ShellyDevice(
        model="SPSW-002XE16EU",
        name="Shelly Pro 2",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-102XE16EU": ShellyDevice(
        model="SPSW-102XE16EU",
        name="Shelly Pro 2",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-202XE16EU": ShellyDevice(
        model="SPSW-202XE16EU",
        name="Shelly Pro 2",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-002PE16EU": ShellyDevice(
        model="SPSW-002PE16EU",
        name="Shelly Pro 2PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-202PE16EU": ShellyDevice(
        model="SPSW-202PE16EU",
        name="Shelly Pro 2PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-003XE16EU": ShellyDevice(
        model="SPSW-003XE16EU",
        name="Shelly Pro 3",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-004PE16EU": ShellyDevice(
        model="SPSW-004PE16EU",
        name="Shelly Pro 4PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSW-104PE16EU": ShellyDevice(
        model="SPSW-104PE16EU",
        name="Shelly Pro 4PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPDM-001PE01EU": ShellyDevice(
        model="SPDM-001PE01EU",
        name="Shelly Pro Dimmer 1PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPDM-002PE01EU": ShellyDevice(
        model="SPDM-002PE01EU",
        name="Shelly Pro Dimmer 2PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPSH-002PE16EU": ShellyDevice(
        model="SPSH-002PE16EU",
        name="Shelly Pro Dual Cover PM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPEM-002CEBEU50": ShellyDevice(
        model="SPEM-002CEBEU50",
        name="Shelly Pro EM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPEM-003CEBEU": ShellyDevice(
        model="SPEM-003CEBEU",
        name="Shelly Pro 3EM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPEM-003CEBEU120": ShellyDevice(
        model="SPEM-003CEBEU120",
        name="Shelly Pro 3EM",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SPEM-003CEBEU400": ShellyDevice(
        model="SPEM-003CEBEU400",
        name="Shelly Pro 3EM-400",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "SAWD-0A1XX10EU1": ShellyDevice(
        model="SAWD-0A1XX10EU1",
        name="Shelly Wall Display",
        min_fw_date=GEN2_MIN_FIRMWARE_DATE,
        gen=GEN2,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SW-001X16EU": ShellyDevice(
        model="S3SW-001X16EU",
        name="Shelly 1 Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SW-001X8EU": ShellyDevice(
        model="S3SW-001X8EU",
        name="Shelly 1 Mini Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SW-001P16EU": ShellyDevice(
        model="S3SW-001P16EU",
        name="Shelly 1PM Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SW-001P8EU": ShellyDevice(
        model="S3SW-001P8EU",
        name="Shelly 1PM Mini Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SW-002P16EU": ShellyDevice(
        model="S3SW-002P16EU",
        name="Shelly 2PM Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3DM-0010WW": ShellyDevice(
        model="S3DM-0010WW",
        name="Shelly Dimmer 0/1-10V PM Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SN-0U12A": ShellyDevice(
        model="S3SN-0U12A",
        name="Shelly H&T Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3SN-0024X": ShellyDevice(
        model="S3SN-0024X",
        name="Shelly I4 Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3PM-001PCEU16": ShellyDevice(
        model="S3PM-001PCEU16",
        name="Shelly PM Mini Gen3",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
    "S3MX-0A": ShellyDevice(
        model="S3MX-0A",
        name="Shelly X MOD1",
        min_fw_date=GEN3_MIN_FIRMWARE_DATE,
        gen=GEN3,
        supported=True,
        gen1_light_transition=False,
    ),
}

GEN1_MODELS_SUPPORTING_LIGHT_TRANSITION = {
    data.model
    for data in DEVICES.values()
    if data.gen1_light_transition and data.gen == 1
}

GEN1_MODELS_UNSUPPORTED = {
    data.model for data in DEVICES.values() if not data.supported and data.gen == 1
}

MODEL_NAMES = {data.model: data.name for data in DEVICES.values()}

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

BLOCK_GENERATIONS = {GEN1}
RPC_GENERATIONS = {GEN2, GEN3}

DEFAULT_HTTP_PORT = 80
PERIODIC_COAP_TYPE_CODE = 30
END_OF_OPTIONS_MARKER = 0xFF

FIRMWARE_PATTERN = re.compile(r"^(\d{8})")

VIRTUAL_COMPONENTS = {"boolean", "button", "enum", "number", "text"}
# Firmware 1.2.0 release date
VIRTUAL_COMPONENTS_MIN_FIRMWARE = 20240213
