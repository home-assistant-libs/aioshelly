"""Shelly Gen2+ BLE support."""
from __future__ import annotations

BLE_SCAN_RESULT_EVENT = "ble.scan_result"

BLE_SCRIPT_NAME = "aioshelly_ble_integration"

BLE_SCAN_RESULT_VERSION = 2

VAR_EVENT_TYPE = "%event_type%"
VAR_ACTIVE = "%active%"
VAR_VERSION = "%version%"
VAR_INTERVAL_MS = "%interval_ms%"
VAR_WINDOW_MS = "%window_ms%"
VAR_DURATION_MS = "%duration_ms%"

DEFAULT_INTERVAL_MS = 320
DEFAULT_WINDOW_MS = 30
DEFAULT_DURATION_MS = -1

BLE_CODE = """
// aioshelly BLE script 2.0
const queueServeTimer = 100; // in ms, timer for events emitting
const burstSendCount =  5; // number if events, emitted on timer event
const maxQueue =  32; // if the queue exceeds the limit, all new events are ignored until it empties
const packetsInSingleEvent = 16; // max number of packets in single event

let queue = [];
let timerHandler = null;

function timerCallback() {
  for(let i = 0; i < burstSendCount; i++) {
    if (queue.length <= 0) {
      break;
    }

    Shelly.emitEvent(
      "%event_type%", [
        %version%,
        queue.slice(0, packetsInSingleEvent),
      ]
    );
    queue = queue.slice(packetsInSingleEvent);
  }

  timerHandler = null;
  if (queue.length > 0) {
    timerHandler = Timer.set(queueServeTimer, false, timerCallback);
  }
}

function bleCallback(event, res) {
  if (event !== BLE.Scanner.SCAN_RESULT) {
    return
  }

  if (queue.length > maxQueue) {
    return;
  }

  queue.push([
    res.addr,
    res.rssi,
    btoa(res.advData),
    btoa(res.scanRsp)
  ]);

  if(!timerHandler) {
    timerHandler = Timer.set(queueServeTimer, false, timerCallback);
  }
}

// Skip starting if scanner is active
if (!BLE.Scanner.isRunning()) {
  BLE.Scanner.Start({
    duration_ms: %duration_ms%,
    active: %active%,
    interval_ms: %interval_ms%,
    window_ms: %window_ms%,
  });
}

BLE.Scanner.Subscribe(bleCallback);
"""
