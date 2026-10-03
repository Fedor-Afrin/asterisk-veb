#!/bin/bash
set -e

APP_DIR="/app"
echo "[*] Инициализация Asterisk Web PBX в директории: $APP_DIR"

cd "$APP_DIR"

# Создаем структуру папок
mkdir -p asterisk/config asterisk/sounds

# Скачиваем и распаковываем конфиги с GitHub «на лету» из открытого репозитория
if [ ! -f "asterisk/config/sip.conf" ]; then
    echo "[*] Загружаем конфигурационные файлы Asterisk..."
    curl -L https://github.com/Fedor-Afrin/asterisk-veb/archive/refs/heads/main.tar.gz -o /tmp/repo.tar.gz
    tar -xzf /tmp/repo.tar.gz -C /tmp --wildcards '*/asterisk/config/*'
    cp -r /tmp/asterisk-veb-main/asterisk/config/* asterisk/config/
    rm -rf /tmp/repo.tar.gz /tmp/asterisk-veb-main
fi

# Создаем файл docker-compose.prod.yml на месте, если его нет
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "[*] Создаем docker-compose.prod.yml..."
    cat << 'EOF' > docker-compose.prod.yml
version: '3.8'

services:
  backend:
    image: ghcr.io/fedor-afrin/asterisk-veb-backend:latest
    container_name: pbx_backend_prod
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./frontend:/frontend
      - ./asterisk/config:/etc/asterisk
      - ./asterisk/sounds:/app/sounds
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/asterisk_pbx
    depends_on:
      - db
    restart: always

  db:
    image: postgres:15-alpine
    container_name: pbx_db_prod
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=asterisk_pbx
    volumes:
      - postgres_data_prod:/var/lib/postgresql/data
    restart: always

  asterisk:
    image: ghcr.io/fedor-afrin/asterisk-veb-asterisk:latest
    container_name: asterisk-pbx-prod
    network_mode: host
    volumes:
      - ./asterisk/config:/etc/asterisk
      - ./asterisk/config/certs:/etc/asterisk/certs:ro
      - ./asterisk/sounds:/usr/share/asterisk/sounds/custom
    restart: always

  coturn:
    image: coturn/coturn
    container_name: coturn-server-prod
    network_mode: host
    volumes:
      - ./asterisk/coturn/turnserver.conf:/etc/coturn/turnserver.conf
    restart: always

volumes:
  postgres_data_prod:
EOF
fi

echo "[*] Развертывание файлов завершено успешно!"