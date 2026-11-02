#!/bin/bash
set -euo pipefail

APP_DIR="/app"
REPO_URL="https://github.com/Fedor-Afrin/asterisk-veb"
BRANCH="main"

mkdir -p "$APP_DIR"
cd "$APP_DIR"
echo "[*] Initializing Asterisk Web PBX..."

curl -fsSL "$REPO_URL/archive/refs/heads/$BRANCH.tar.gz" -o /tmp/asterisk-veb.tar.gz
tar -xzf /tmp/asterisk-veb.tar.gz -C /tmp
SOURCE_DIR="/tmp/asterisk-veb-$BRANCH"

cp -a "$SOURCE_DIR/backend" "$APP_DIR/"
cp -a "$SOURCE_DIR/frontend" "$APP_DIR/"
cp -a "$SOURCE_DIR/asterisk" "$APP_DIR/"
cp "$SOURCE_DIR/docker-compose.prod.yml" "$APP_DIR/docker-compose.yml"
cp "$SOURCE_DIR/.env.example" "$APP_DIR/.env.example"

rm -rf /tmp/asterisk-veb.tar.gz "$SOURCE_DIR"

echo
echo "Installation files are ready. Before starting the stack:"
echo "  1. cd $APP_DIR"
echo "  2. cp .env.example .env"
echo "  3. Edit .env and set unique passwords/secrets"
echo "  4. Configure a matching AMI secret in asterisk/config/manager.conf"
echo "  5. Install your own TLS certificate and private key if using SIP-TLS"
echo "  6. Configure a TURN realm, secret, and public IP if using CoTURN"
echo "  7. docker compose up -d"
echo
echo "Do not commit .env, certificates, or private recordings."
