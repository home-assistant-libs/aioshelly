"""Constants for aioshelly."""

MODEL_NAMES = {
    # Gen1 CoAP based models
    "SH2LED-1": "Shelly 2LED",
    "SHAIR-1": "Shelly Air",
    "SHBDUO-1": "Shelly DUO",
    "SHBLB-1": "Shelly Bulb",
    "SHBTN-1": "Shelly Button1",
    "SHBTN-2": "Shelly Button1",  # hw v2
    "SHBVIN-1": "Shelly Vintage",
    "SHCB-1": "Shelly Bulb RGBW",
    "SHCL-255": "Shelly Color",
    "SHDIMW-1": "Shelly Dimmer W1",
    "SHDM-1": "Shelly Dimmer",
    "SHDM-2": "Shelly Dimmer 2",
    "SHDW-1": "Shelly Door/Window",
    "SHDW-2": "Shelly Door/Window 2",
    "SHEM": "Shelly EM",
    "SHEM-3": "Shelly 3EM",
    "SHGS-1": "Shelly Gas",
    "SHHT-1": "Shelly H&T",
    "SHIX3-1": "Shelly i3",
    "SHMOS-01": "Shelly Motion",
    "SHPLG-1": "Shelly Plug",
    "SHPLG-S": "Shelly Plug S",
    "SHPLG-U1": "Shelly Plug US",
    "SHPLG2-1": "Shelly Plug E",
    "SHRGBW2": "Shelly RGBW2",
    "SHRGBWW-01": "Shelly RGBW",
    "SHSEN-1": "Shelly Sense",  # CoAP v1, unsupported
    "SHSM-01": "Shelly Smoke",
    "SHSM-02": "Shelly Smoke 2",
    "SHSPOT-1": "Shelly Spot",
    "SHSPOT-2": "Shelly Spot 2",
    "SHSW-1": "Shelly 1",
    "SHSW-21": "Shelly 2",
    "SHSW-25": "Shelly 2.5",
    "SHSW-44": "Shelly 4Pro",  # CoAP v1, unsupported
    "SHSW-L": "Shelly 1L",
    "SHSW-PM": "Shelly 1PM",
    "SHUNI-1": "Shelly UNI",
    "SHVIN-1": "Shelly Vintage",
    "SHWT-1": "Shelly Flood",
    # Gen2 RPC based models
    "SNSW-001P16EU": "Shelly Plus 1PM",
    "SNSW-001X16EU": "Shelly Plus 1",
    "SPSW-004PE16EU": "Shelly Pro 4PM",
}

# Timeout used for Block Device init
BLOCK_DEVICE_INIT_TIMEOUT = 10

# Firmware 1.8.0 release date (CoAP v2)
GEN1_MIN_FIRMWARE_DATE = 20200812

# WebScoket receive timeout - used for Heartbeat ping/pong
WS_RECEIVE_TIMEOUT = 50

# Notification sent by RPC device in case of WebSocket close
NOTIFY_WS_CLOSED = "NotifiyWebSocketClosed"
