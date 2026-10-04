#!/bin/bash
set -e

APP_DIR="/app"
echo "[*] Initializing Asterisk Web PBX project..."

cd "$APP_DIR"

# 1. Скачиваем и распаковываем весь репозиторий с GitHub на лету
echo "[*] Downloading project files from GitHub..."
curl -L https://github.com/Fedor-Afrin/asterisk-veb/archive/refs/heads/main.tar.gz -o /tmp/repo.tar.gz
tar -xzf /tmp/repo.tar.gz -C /tmp

# Копируем бэкенд, фронтенд и астериск в рабочую директорию
cp -r /tmp/asterisk-veb-main/backend .
cp -r /tmp/asterisk-veb-main/frontend .
cp -r /tmp/asterisk-veb-main/asterisk .

# 2. Скачиваем docker-compose.prod.yml и сразу сохраняем как стандартный docker-compose.yml
echo "[*] Setting up configuration files..."
curl -L https://raw.githubusercontent.com/Fedor-Afrin/asterisk-veb/main/docker-compose.prod.yml -o docker-compose.yml

# Очистка временных архивов
rm -rf /tmp/repo.tar.gz /tmp/asterisk-veb-main

# 3. Информационное сообщение для пользователя на английском языке
echo ""
echo "=================================================================="
echo " Installation completed successfully! 🎉"
echo "=================================================================="
echo " To start your project, please run the following commands:"
echo ""
echo "   cd ~/asterisk-veb"
echo "   docker compose up -d"
echo ""
echo "=================================================================="