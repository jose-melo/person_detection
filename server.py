from flask import Flask, request, render_template, send_from_directory
import os

app = Flask(__name__)

# Diretório para salvar as imagens
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Rota para receber e salvar a imagem
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'Nenhum arquivo enviado', 400

    file = request.files['file']
    if file.filename == '':
        return 'Nenhum arquivo selecionado', 400

    if file:
        filename = 'last_image.jpg'  # Salvamos sempre com o mesmo nome para manter apenas a última imagem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return 'Imagem recebida com sucesso', 200

# Rota para fornecer a página web com a última imagem
@app.route('/')
def show_image():
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'last_image.jpg')
    if os.path.exists(image_path):
        return render_template('image.html', image_path=image_path)
    else:
        return 'Nenhuma imagem disponível', 404

# Rota para acessar diretamente a imagem
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Inicializando o diretório de uploads
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if __name__ == '__main__':
    app.run(debug=True)
