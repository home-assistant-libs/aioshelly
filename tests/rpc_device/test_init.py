from aioshelly import rpc_device


def test_exports() -> None:
    """Test objects are available at top level of rpc_device."""
    assert hasattr(rpc_device, "bluetooth_mac_from_primary_mac")
    assert hasattr(rpc_device, "RpcDevice")
    assert hasattr(rpc_device, "RpcUpdateType")
    assert hasattr(rpc_device, "WsServer")
