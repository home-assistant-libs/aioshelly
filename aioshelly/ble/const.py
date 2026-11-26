"""Shelly Gen2+ BLE support."""

from __future__ import annotations

BLE_SCAN_RESULT_EVENT = "ble.scan_result"

BLE_SCRIPT_NAME = "aioshelly_ble_integration"

BLE_SCAN_RESULT_VERSION = 2

VAR_EVENT_TYPE = "%event_type%"
VAR_ACTIVE = "%active%"
VAR_VERSION = "%version%"

BLE_CODE = """
// aioshelly BLE script 2.1
// Script automatically installed by Home Assistant for Bluetooth proxy support
// https://www.home-assistant.io/integrations/bluetooth/#remote-adapters-bluetooth-proxies
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


BLE_CODE_X2I = """// aioshelly Wall Display X2i compatibility
// CloudRelay BTHome gateway

var alphabet =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

var seen = {};
var busy = false;

function decode64(s) {
  var bytes = [];
  var buffer = 0;
  var bits = 0;

  for (var i = 0; i < s.length; i++) {
    var v = alphabet.indexOf(s.charAt(i));
    if (v < 0) continue;

    buffer = (buffer << 6) | v;
    bits += 6;

    if (bits >= 8) {
      bits -= 8;
      bytes.push((buffer >> bits) & 255);
    }
  }

  return bytes;
}

function encode64(bytes) {
  var out = "";

  for (var i = 0; i < bytes.length; i += 3) {
    var a = bytes[i];
    var b = i + 1 < bytes.length ? bytes[i + 1] : 0;
    var c = i + 2 < bytes.length ? bytes[i + 2] : 0;

    out += alphabet.charAt(a >> 2);
    out += alphabet.charAt(((a & 3) << 4) | (b >> 4));

    out += i + 1 < bytes.length
      ? alphabet.charAt(((b & 15) << 2) | (c >> 6))
      : "=";

    out += i + 2 < bytes.length
      ? alphabet.charAt(c & 63)
      : "=";
  }

  return out;
}

// Compatibility with aioshelly scan-mode RPC.
// CloudRelay does not expose active scan control.
function setActive(v) {
  return JSON.stringify(true);
}

function poll() {
  if (busy) return;
  busy = true;

  Shelly.call(
    "BLE.CloudRelay.ListInfos",
    {},
    function(result, error_code, error_message) {
      busy = false;

      if (error_code !== 0 || !result) return;
      if (!result.devices) return;

      var packets = [];

      for (var i = 0; i < result.devices.length; i++) {
        var device = result.devices[i];
        var mac = Object.keys(device)[0];
        var info = device[mac];

        if (!info.sdata || !info.sdata.fcd2) continue;

        if (typeof result.ts !== "number") continue;
        if (typeof info.last_seen !== "number") continue;

        var age = result.ts - info.last_seen;
        if (age > 60 || age < 0) continue;

        var signature =
          info.last_seen + ":" + info.sdata.fcd2;

        if (seen[mac] === signature) continue;

        var payload = decode64(info.sdata.fcd2);

        if (payload.length === 0) continue;
        if (payload.length > 252) continue;

        var adv = [payload.length + 3, 22, 210, 252];

        for (var j = 0; j < payload.length; j++) {
          adv.push(payload[j]);
        }

        packets.push([
          mac,
          -90,
          encode64(adv),
          ""
        ]);

        seen[mac] = signature;
      }

      if (packets.length > 0) {
        Shelly.emitEvent("ble.scan_result", {
          version: 2,
          packets: packets
        });
      }
    }
  );
}

Timer.set(5000, true, poll);
poll();"""
