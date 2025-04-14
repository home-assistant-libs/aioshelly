from aioshelly import block_device


def test_exports() -> None:
    """Test objects are available at top level of block_device."""
    assert hasattr(block_device, "BLOCK_VALUE_UNIT")
    assert hasattr(block_device, "COAP")
    assert hasattr(block_device, "Block")
    assert hasattr(block_device, "BlockDevice")
    assert hasattr(block_device, "BlockUpdateType")
