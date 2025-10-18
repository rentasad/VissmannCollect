FROM python:3.12-slim

# System deps (optional; nur bei Bedarf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App rein
COPY app ./app
COPY tokens.json ./tokens.json
# optional, wenn du lokal schon welche hast
# Für lokale Läufe kannst du tokens.json auch als Volume mounten

ENV PYTHONUNBUFFERED=1

# Default-Command: einfach main.py starten
CMD ["python", "-m", "app.main"]
