"""Shelly Gen2+ BLE support."""
from __future__ import annotations

BLE_SCAN_RESULT_EVENT = "ble.scan_result"

BLE_SCRIPT_NAME = "aioshelly_ble_integration"

BLE_SCAN_RESULT_VERSION = 1

VAR_EVENT_TYPE = "%event_type%"
VAR_ACTIVE = "%active%"
VAR_VERSION = "%version%"

BLE_CODE = """
// aioshelly BLE script 2.0
const queueServeTimer = 450; // in ms, timer for events emitting
const burstSendCount =  5; // number if events, emitted on timer event
const maxQueue =  80; // if the queue exceeds the limit, all new events are ignored until it empties

let queue = [];
let timerHandler = null;

function timerCallback() {  
  Timer.clear(timerHandler);
  
  for(let i = 0; i < burstSendCount; i++) {
    if (queue.length <= 0) {
      break;
    }

    Shelly.emitEvent("%event_type%", queue[0]);
    queue = queue.slice(1);
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
    %version%,
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
    duration_ms: -1,
    active: %active%,
  });
}

BLE.Scanner.Subscribe(bleCallback);
"""
