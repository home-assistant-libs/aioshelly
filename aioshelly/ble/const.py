"""Shelly Gen2+ BLE support."""

from __future__ import annotations

BLE_SCAN_RESULT_EVENT = "ble.scan_result"

BLE_SCRIPT_NAME = "aioshelly_ble_integration"

BLE_SCAN_RESULT_VERSION = 2

VAR_EVENT_TYPE = "%event_type%"
VAR_ACTIVE = "%active%"
VAR_VERSION = "%version%"
VAR_ALLOWED_ADDRESSES = "%allowed_addresses%"
VAR_MIN_RSSI = "%min_rssi%"
VAR_MIN_INTERVAL_MS = "%min_interval_ms%"

BLE_CODE = """
// aioshelly BLE script 2.2
// Script automatically installed by Home Assistant for Bluetooth proxy support
// https://www.home-assistant.io/integrations/bluetooth/#remote-adapters-bluetooth-proxies
const queueServeTimer = 100; // in ms, timer for events emitting
const burstSendCount =  5; // number if events, emitted on timer event
const maxQueue =  32; // if the queue exceeds the limit, all new events are ignored until it empties
const packetsInSingleEvent = 16; // max number of packets in single event


// Optional advertisement filter. Dropping advertisements on the device
// keeps them off the network link, which matters on metered or slow
// links (LTE, VPN) and in busy BLE environments.
// null = forward everything, otherwise {"aa:bb:cc:dd:ee:ff": true}
const allowedAddresses = %allowed_addresses%;
const minRssi = %min_rssi%; // in dBm, null = no limit
// Forward at most one advertisement per address in this period;
// 0 = no limit. Only applied when allowedAddresses is set, which
// keeps the per-address state bounded.
const minIntervalMs = %min_interval_ms%;

let queue = [];
let timerHandler = null;
let lastForwarded = {};

function nowMs() {
  if (typeof Shelly.getUptimeMs === 'function') {
    return Shelly.getUptimeMs();
  }
  return Date.now();
}

function isFiltered(res) {
  if (minRssi !== null && res.rssi < minRssi) {
    return true;
  }
  if (allowedAddresses === null) {
    return false;
  }
  if (allowedAddresses[res.addr] !== true) {
    return true;
  }
  if (minIntervalMs > 0) {
    let now = nowMs();
    let last = lastForwarded[res.addr];
    if (typeof last === 'number' && now >= last && now - last < minIntervalMs) {
      return true;
    }
    lastForwarded[res.addr] = now;
  }
  return false;
}

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
    return;
  }

  if (isFiltered(res)) {
    return;
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

// Flip the scanner's active mode at runtime via Script.Eval; this is
// how on-demand active scan windows avoid rewriting the script body
// (and thus avoid a flash write) on every transition.
//
// Two device quirks shape this dance:
//   1. The scanner stop is asynchronous - a start issued in the
//      same JS frame races with the still-in-progress stop and
//      silently fails. Defer start onto a Timer so the underlying BLE
//      stack has time to settle.
//   2. The scan subscription does NOT survive a stop/start cycle -
//      the subscription is dropped on stop and must be re-attached
//      after each start, or no scan results will be delivered.
//
// The scanner method casing also differs by device family: gen2+
// firmware exposes Start/Stop capitalized and subscribe lowercase,
// while the Android-based Wall Display exposes start/stop lowercase.
// The wrappers below call whichever variant the device provides.
function scannerStart(options) {
  if (typeof BLE.Scanner.start === 'function') {
    BLE.Scanner.start(options);
  } else {
    BLE.Scanner.Start(options);
  }
}

function scannerStop() {
  if (typeof BLE.Scanner.stop === 'function') {
    BLE.Scanner.stop();
  } else {
    BLE.Scanner.Stop();
  }
}

function scannerSubscribe(callback) {
  if (typeof BLE.Scanner.subscribe === 'function') {
    BLE.Scanner.subscribe(callback);
  } else {
    BLE.Scanner.Subscribe(callback);
  }
}

let pendingActive = null;
function applyPendingActive() {
  if (pendingActive === null) {
    return;
  }
  scannerStart({
    duration_ms: -1,
    active: pendingActive,
  });
  scannerSubscribe(bleCallback);
  pendingActive = null;
}

function setActive(v) {
  pendingActive = v;
  if (BLE.Scanner.isRunning()) {
    scannerStop();
    Timer.set(250, false, applyPendingActive);
  } else {
    applyPendingActive();
  }
}

setActive(%active%);
"""  # noqa: E501
