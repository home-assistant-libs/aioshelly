"""Powered by Shelly object structures."""

from typing import Any

OBJECT_STRUCTURES: dict[str, dict[str, Any]] = {
    "FK-06X": {
        "zone0": {
            "name": "Zone 1",
            "index": 200,
            "type": "number",
            "key": "duration",
            "unit": "min",
        },
        "zone1": {
            "name": "Zone 2",
            "index": 201,
            "type": "number",
            "key": "duration",
            "unit": "min",
        },
        "zone2": {
            "name": "Zone 3",
            "index": 202,
            "type": "number",
            "key": "duration",
            "unit": "min",
        },
        "zone3": {
            "name": "Zone 4",
            "index": 203,
            "type": "number",
            "key": "duration",
            "unit": "min",
        },
        "zone4": {
            "name": "Zone 5",
            "index": 204,
            "type": "number",
            "key": "duration",
            "unit": "min",
        },
        "zone5": {
            "name": "Zone 6",
            "index": 205,
            "type": "number",
            "key": "duration",
            "unit": "min",
        },
    },
    "EVE01-11": {
        "counter": {
            "name": "Counter",
            "index": 200,
            "type": "number",
            "key": "total",
            "unit": "count",
        },
        "total_current": {
            "name": "Total Current",
            "index": 201,
            "type": "number",
            "key": "total_current",
            "unit": "A",
        },
        "total_power": {
            "name": "Total Power",
            "index": 202,
            "type": "number",
            "key": "total_power",
            "unit": "W",
        },
        "total_act_energy": {
            "name": "Total Active Energy",
            "index": 203,
            "type": "number",
            "key": "total_act_energy",
            "unit": "Wh",
        },
        "phase_a": {
            "name": "Phase A",
            "index": 204,
            "type": "number",
            "key": "voltage",
            "unit": "V",
        },
        "phase_b": {
            "name": "Phase B",
            "index": 205,
            "type": "number",
            "key": "voltage",
            "unit": "V",
        },
        "phase_c": {
            "name": "Phase C",
            "index": 206,
            "type": "number",
            "key": "voltage",
            "unit": "V",
        },
    },
}
