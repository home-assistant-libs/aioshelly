import pytest

from aioshelly.rpc_device.utils import (
    bluetooth_mac_from_primary_mac,
    parse_sdp_ice_credentials,
)


def test_bluetooth_mac_from_primary_mac() -> None:
    """Test bluetooth_mac_from_primary_mac."""
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4E5F") == "0A1B2C3D4E61"
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4EA0") == "0A1B2C3D4EA2"
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4EF0") == "0A1B2C3D4EF2"
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4EC9") == "0A1B2C3D4ECB"


def test_parse_sdp_ice_credentials() -> None:
    """Test parse_sdp_ice_credentials with valid SDP."""
    sdp = (
        "v=0\r\n"
        "o=mozilla...THIS_IS_SDPARTA-99.0 460215425073074024 0 IN IP4 0.0.0.0\r\n"
        "s=-\r\n"
        "t=0 0\r\n"
        "a=ice-ufrag:abc123\r\n"
        "a=ice-pwd:def456\r\n"
        "m=audio 9 UDP/TLS/RTP/SAVPF 109 9 0 8 101\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 120 124 121 125 126 127 97 99 100 123 122 119\r\n"
        "c=IN IP4 0.0.0.0\r\n"
    )
    assert parse_sdp_ice_credentials(sdp) == ("abc123", "def456")


@pytest.mark.parametrize(
    "sdp",
    [
        "v=0\r\na=ice-pwd:def456\r\n",
        "v=0\r\na=ice-ufrag:abc123\r\n",
        "v=0\r\no=- 123 456 IN IP4 192.168.1.1\r\ns=-\r\n",
    ],
)
def test_parse_sdp_ice_credentials_error(sdp: str) -> None:
    """Test parse_sdp_ice_credentials with missing ice-ufrag."""
    with pytest.raises(ValueError, match="Missing ice-ufrag or ice-pwd in SDP"):
        parse_sdp_ice_credentials(sdp)
