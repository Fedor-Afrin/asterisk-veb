#!/bin/bash
set -e

APP_DIR="/app"
echo "[*] Инициализация полного пакета Asterisk Web PBX..."

cd "$APP_DIR"

# 1. Скачиваем и распаковываем весь репозиторий с GitHub на лету
echo "[*] Загружаем файлы проекта с GitHub..."
curl -L https://github.com/Fedor-Afrin/asterisk-veb/archive/refs/heads/main.tar.gz -o /tmp/repo.tar.gz
tar -xzf /tmp/repo.tar.gz -C /tmp

# Копируем бэкенд, фронтенд и астериск в рабочую директорию
cp -r /tmp/asterisk-veb-main/backend .
cp -r /tmp/asterisk-veb-main/frontend .
cp -r /tmp/asterisk-veb-main/asterisk .

# 2. Скачиваем файл композа из репозитория и СРАЗУ сохраняем как стандартный docker-compose.yml
echo "[*] Разворачиваем конфигурацию Docker Compose..."
curl -L https://raw.githubusercontent.com/Fedor-Afrin/asterisk-veb/main/docker-compose.prod.yml -o docker-compose.yml

# 3. Автоматически запускаем стек контейнеров через сокет хоста
echo "[*] Запуск Docker Compose..."
docker compose up -d

# Очистка временных файлов
rm -rf /tmp/repo.tar.gz /tmp/asterisk-veb-main

echo "[✨] Установка и запуск успешно завершены!"