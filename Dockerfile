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
ENV TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ENV BING_API_KEY=your_bing_api_key

# Perintah untuk menjalankan aplikasi
CMD ["python", "app.py"]
