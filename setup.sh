#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

echo "1. Создаем структуру директорий..."
mkdir -p backend asterisk/config

echo "2. Создаем docker-compose.yml..."
cat << 'EOF' > docker-compose.yml
services:
  db:
    image: postgres:15-alpine
    container_name: pbx_db
    restart: always
    environment:
      POSTGRES_USER: pbx_user
      POSTGRES_PASSWORD: pbx_password
      POSTGRES_DB: pbx_db
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - pbx_net

  backend:
    build: ./backend
    container_name: pbx_backend
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://pbx_user:pbx_password@db:5432/pbx_db
    depends_on:
      - db
      - asterisk
    networks:
      - pbx_net

  asterisk:
    image: andrius/asterisk:latest
    container_name: pbx_asterisk
    restart: always
    network_mode: host
    volumes:
      - ./asterisk/config:/etc/asterisk

volumes:
  pgdata:

networks:
  pbx_net:
    driver: bridge
EOF

echo "3. Создаем backend/requirements.txt..."
cat << 'EOF' > backend/requirements.txt
fastapi==0.110.0
uvicorn==0.28.0
sqlalchemy==2.0.28
asyncpg==0.29.0
pydantic==2.6.4
slowapi==0.1.9
panoramisk==1.3
EOF

echo "4. Создаем backend/Dockerfile..."
cat << 'EOF' > backend/Dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main.py:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

echo "5. Создаем backend/main.py..."
cat << 'EOF' > backend/main.py
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Asterisk Web Management API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/")
@limiter.limit("5/minute")
async def root(request: Request):
    return {"status": "ok", "message": "Asterisk PBX API is running"}
EOF

echo "6. Запускаем проект через Docker Compose..."
docker compose up --build -d

echo "Готово! Проект запущен. API доступен по адресу: http://localhost:8000"
