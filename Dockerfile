# Menggunakan image Python sebagai base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Salin file requirements.txt dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file aplikasi ke dalam container
COPY . .

# Set variabel lingkungan
ENV TELEGRAM_BOT_TOKEN=7939254454:AAEhQNCUW6PJunraVtJ5HICB-DpJfmBMeTo
ENV BING_API_KEY=04dc7865095c4d029369f8ebff18d43a
ENV LOGGING_LEVEL=INFO
ENV TTS_LANGUAGE=id

# Perintah untuk menjalankan aplikasi
CMD ["python", "app.py"]
