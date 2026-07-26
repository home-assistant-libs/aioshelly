from aioshelly.rpc_device.utils import bluetooth_mac_from_primary_mac


def test_bluetooth_mac_from_primary_mac() -> None:
    """Test bluetooth_mac_from_primary_mac."""
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4E5F") == "0A1B2C3D4E61"
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4EA0") == "0A1B2C3D4EA2"
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4EF0") == "0A1B2C3D4EF2"
    assert bluetooth_mac_from_primary_mac("0A1B2C3D4EC9") == "0A1B2C3D4ECB"
