# Menggunakan image Python sebagai base image
FROM python:3.12-slim

# Install ketergantungan sistem yang diperlukan
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Salin file requirements.txt dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file aplikasi ke dalam container
COPY . .

# Set variabel lingkungan
ENV TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ENV BING_API_KEY=your_bing_api_key
ENV LOGGING_LEVEL=INFO
ENV TTS_LANGUAGE=id

# Perintah untuk menjalankan aplikasi
CMD ["python", "app.py"]
