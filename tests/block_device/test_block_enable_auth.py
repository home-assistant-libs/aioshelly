import asyncio
import aiohttp
from aioshelly.block_device import BlockDevice, COAP
from aioshelly.common import ConnectionOptions

# Configuration - set these values for tests
DEVICE_IP = "192.168.x.x"
USERNAME = "admin"
PASSWORD = "TestPassword123"

async def test():
    print("Starting...")
    
    print("Initializing CoAP context...")
    async with COAP() as coap:
        print("CoAP context ready")
        
        async with aiohttp.ClientSession() as session:
            print(f"Connecting to device at {DEVICE_IP}...")
            device = await BlockDevice.create(session, coap, DEVICE_IP)
            
            print("Initializing device...")
            await device.initialize()
            
            print(f"Device: {device.model}")
            print(f"Auth enabled: {device.requires_auth}")
            
            input("Press Enter to ENABLE authentication...")
            result = await device.set_auth(USERNAME, PASSWORD)
            print(f"Authentication enabled!")
            print(f"Response: {result}")

asyncio.run(test())
