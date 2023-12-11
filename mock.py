import cv2
import numpy as np
import requests
import os

# URL do endpoint de upload no servidor Flask
UPLOAD_URL = 'http://localhost:5000/upload'

# Criar uma imagem de exemplo em NumPy (aqui, um array 100x100 com cor aleatória)
image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

# Salvar a imagem NumPy temporariamente como um arquivo PNG
temp_image_path = 'temp_image.png'
cv2.imwrite(temp_image_path, image)

# Fazer o upload do arquivo
with open(temp_image_path, 'rb') as f:
    response = requests.post(UPLOAD_URL, files={'file': f})

# Verificar a resposta do servidor
if response.status_code == 200:
    print('Upload realizado com sucesso.')
else:
    print('Falha no upload:', response.text)

# Remover o arquivo temporário
os.remove(temp_image_path)
