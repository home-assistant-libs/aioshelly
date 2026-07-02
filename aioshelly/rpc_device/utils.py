"""Utilities for RPC devices."""

from __future__ import annotations

# The Bluetooth MAC address is the primary MAC address plus 2.
# https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/misc_system_api.html#mac-address


def bluetooth_mac_from_primary_mac(primary_mac: str) -> str:
    """Get Bluetooth MAC from primary MAC.

    MAC address must be in format "[0-F]{16}"

    :param primary_mac: Primary MAC address
    :return: Bluetooth MAC address
    """
    return f"{(int(primary_mac, 16) + 2):012X}"


def parse_sdp_ice_credentials(sdp: str) -> tuple[str, str]:
    """Extract ice-ufrag and ice-pwd from an SDP string."""
    ufrag = ""
    pwd = ""
    for line in sdp.splitlines():
        if line.startswith("a=ice-ufrag:"):
            ufrag = line[12:]
        elif line.startswith("a=ice-pwd:"):
            pwd = line[10:]
    if not ufrag or not pwd:
        raise ValueError("Missing ice-ufrag or ice-pwd in SDP")
    return ufrag, pwd
