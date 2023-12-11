import numpy as np
import matplotlib.pyplot as plt
import asyncio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakDBusError
from tqdm import tqdm

DEVICE_NAME = "Nano 33 IoT"
LED_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
LED_CHAR_UUID = "00002a57-0000-1000-8000-00805f9b34fb"
CTL_CHAR_UUID = "00002a58-0000-1000-8000-00805f9b34fb"


IMG_SIZE = 96
CHUNK_SIZE = 50  # Adjust as per your actual chunk size

pixel_idx = -1
img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
recv_buffer = []  # List to store received bytes
progress_bar = tqdm(total=IMG_SIZE * IMG_SIZE, desc="Receiving Image", position=0, leave=True)

def process_buffer():
    global pixel_idx, img, recv_buffer
    while len(recv_buffer) > 0:  # Process all bytes in buffer
        chunk = recv_buffer[:CHUNK_SIZE]  # Extract up to CHUNK_SIZE bytes
        del recv_buffer[:CHUNK_SIZE]  # Remove the processed bytes

        for byte in chunk:
            pixel_idx += 1
            progress_bar.update(1)
            if pixel_idx == IMG_SIZE * IMG_SIZE:
                plt.imshow(img, cmap='gray', vmin=0, vmax=255)
                plt.show()
                pixel_idx = -1
                progress_bar.reset()
                recv_buffer = [] 
                img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
                break
            else:
                img[pixel_idx // IMG_SIZE, pixel_idx % IMG_SIZE] = byte

def handle_packet(sender, data):
    global recv_buffer
    recv_buffer.extend(data)  # Add the received bytes to the buffer
    process_buffer()  # Process bytes from buffer

async def run():
    global pixel_idx
    global img

    while True:
        choice = int(input("Enter 1 for LED on, any other number for LED off: "))
        if choice == 1:
            # for _ in range(100):
            devices = await BleakScanner.discover()
            
            print(f"Found {len(devices)} devices.")
            for device in devices:
                print(f"  name: {device.name} addr: ({device.address}): {device.metadata} ", device.metadata['uuids'])
                if len(device.metadata['uuids']) > 0 and (LED_SERVICE_UUID in device.metadata['uuids'] or device.name == DEVICE_NAME):
                    async with BleakClient(device.address) as client:
                        print(f"Connected to {device.name}")

                        await client.start_notify(LED_CHAR_UUID, handle_packet)
                        # await client.write_gatt_char(CTL_CHAR_UUID, [choice])
                        await asyncio.sleep((96*96/50)*50/1000)
                        # await client.write_gatt_char(CTL_CHAR_UUID, [0])

                        process_buffer()
                        # Stop notifications
                        await client.stop_notify(LED_CHAR_UUID)

                        # Disconnect
                        await client.disconnect()
                    
loop = asyncio.get_event_loop()

loop.run_until_complete(run())
