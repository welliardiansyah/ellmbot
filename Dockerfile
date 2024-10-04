FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ENV BING_API_KEY=your_bing_api_key
ENV LOGGING_LEVEL=INFO
ENV TTS_LANGUAGE=id

CMD ["python", "app.py"]
