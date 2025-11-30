import asyncio
import aiohttp
from aioshelly.rpc_device import RpcDevice, WsServer
from aioshelly.common import ConnectionOptions

# Configuration - set these values for tests
DEVICE_IP = "192.168.x.x"
PASSWORD = "TestPassword123"

async def test():
    print("Starting...")
    
    ws = WsServer()
    print("Initializing WebSocket server...")
    await ws.initialize(8123)
    print("WebSocket server ready")
    
    async with aiohttp.ClientSession() as session:
        print(f"Connecting to device at {DEVICE_IP} with credentials...")
        opts = ConnectionOptions(DEVICE_IP, "admin", PASSWORD)
        device = await RpcDevice.create(session, ws, opts)
        
        print("Initializing device...")
        await device.initialize()
        
        print(f"Device: {device.shelly['id']}")
        print(f"Auth enabled: {device.requires_auth}")
        
        input("Press Enter to DISABLE authentication...")
        await device.disable_auth()
        print("Authentication disabled!")

asyncio.run(test())
