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

ENV TELEGRAM_BOT_TOKEN=7939254454:AAEhQNCUW6PJunraVtJ5HICB-DpJfmBMeTo
ENV BING_API_KEY=04dc7865095c4d029369f8ebff18d43a
ENV LOGGING_LEVEL=INFO
ENV TTS_LANGUAGE=id

CMD ["python", "app.py"]
