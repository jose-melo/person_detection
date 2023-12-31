from PIL import Image
import numpy as np

import matplotlib.pyplot as plt
import asyncio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakDBusError
from tqdm import tqdm
import requests
import os


DEVICE_NAME = "Nano 33 IoT"
LED_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
LED_CHAR_UUID = "00002a57-0000-1000-8000-00805f9b34fb"
CTL_CHAR_UUID = "00002a58-0000-1000-8000-00805f9b34fb"

BASE_URL = 'http://192.168.116.10:5000'
UPLOAD_URL = f'{BASE_URL}/upload'
DETECT_URL = f'{BASE_URL}/detect'


IMG_SIZE = 96
CHUNK_SIZE = 96  # Adjust as per your actual chunk size

pixel_idx = -1
is_receiving = False
is_receiving_score = False
img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
recv_buffer = []  # List to store received bytes

progress_bar = None 


def post_detection_status(score):
    detected = score > 0  
    data = {'detected': detected}
    try:
        response = requests.post(DETECT_URL, json=data)
        if response.status_code == 200:
            print('Status de detecção enviado com sucesso')
        else:
            print('Falha ao enviar status de detecção')
    except requests.RequestException as e:
        print(f'Erro ao enviar status de detecção: {e}')



def process_buffer():
    global pixel_idx, img, recv_buffer
    global is_receiving
    global is_receiving_score
    global progress_bar
    while len(recv_buffer) > 0:  # Process all bytes in buffer
        chunk = recv_buffer[:CHUNK_SIZE]  # Extract up to CHUNK_SIZE bytes
        del recv_buffer[:CHUNK_SIZE]  # Remove the processed bytes
        

        if is_receiving_score:
            score = int.from_bytes(chunk, byteorder='little')
            post_detection_status(score)
            print(f"Score: {score}")
            is_receiving_score = False
            is_receiving = False
            break
        
        for byte in chunk:
            pixel_idx += 1
            progress_bar.update(1)
            if pixel_idx == IMG_SIZE * IMG_SIZE - 1:
                temp_image_path = 'temp_image.png'
                image = Image.fromarray(img)

                # Save the image
                image.save(temp_image_path)
                
                with open(temp_image_path, 'rb') as f:
                    response = requests.post(UPLOAD_URL, files={'file': f})
                
                
                if response.status_code == 200:
                    print('Upload realizado com sucesso.')
                else:
                    print('Falha no upload:', response.text)
                
                
                os.remove(temp_image_path) 

                #plt.imshow(img, cmap='gray', vmin=0, vmax=255)
                #plt.show()
                #progress_bar.reset()
                is_receiving_score = True
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
    global is_receiving
    global progress_bar
    global recv_buffer

    while True:
        choice = int(input("Digite 1 para tirar uma foto: "))
        if choice == 1:
            adv_data = await BleakScanner.discover(return_adv=True)

            for key, adv in adv_data.items():
                device = adv[0]
                adv_dat = adv[1]
                uuids = adv_dat.service_uuids
                if len(uuids) > 0 and (LED_SERVICE_UUID in uuids or device.name == DEVICE_NAME):
                    
                    try:
                        async with BleakClient(device.address) as client:
                            print(f"Connected to {device.name}")
                            is_receiving = True

                            progress_bar = tqdm(total=IMG_SIZE * IMG_SIZE, desc="Receiving Image", position=0, leave=True)
                            print("Start notify")
                            try:
                                await client.start_notify(LED_CHAR_UUID, handle_packet)
                            except:
                                print("Failed to start notify. Trying again...")
                                await asyncio.sleep(16)
                                break

                            while is_receiving: pass

                            progress_bar.reset()
                            pixel_idx = -1
                            recv_buffer = [] 
                            img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)


                            print("Stop notify")
                            await client.stop_notify(LED_CHAR_UUID)

                            print("Disconnecting...")
                            await client.disconnect()
                    except:
                        break
                        

        

loop = asyncio.get_event_loop()

loop.run_until_complete(run())
