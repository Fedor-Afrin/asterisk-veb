#!/usr/bin/env bash
set -euo pipefail

IN_CONTAINER="${IN_INSTALLER_CONTAINER:-0}"
BRANCH="${BRANCH:-main}"
REPO_URL="https://github.com/Fedor-Afrin/asterisk-veb"
SOURCE_DIR="${SOURCE_DIR:-}"
RESET="${RESET:-0}"
YES="${YES:-0}"

if [ "$IN_CONTAINER" = "1" ]; then
  [ -n "${APP_DIR:-}" ] || { echo "[!] Не задан APP_DIR" >&2; exit 1; }
else
  APP_DIR="${APP_DIR:-$HOME/asterisk-pbx}"
fi

# Запуск из клона репозитория (bash installer/install.sh): берём файлы оттуда, а не из сети
if [ -z "$SOURCE_DIR" ] && [ "$IN_CONTAINER" != "1" ] && [ -f "${BASH_SOURCE[0]:-}" ]; then
  _here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [ -d "$_here/backend" ] && [ -f "$_here/docker-compose.prod.yml" ] && [ -f "$_here/.env.example" ]; then
    SOURCE_DIR="$_here"
  fi
fi

log()  { echo "[*] $*"; }
warn() { echo "[!] $*" >&2; }
die()  { warn "$*"; exit 1; }

rand() { LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 48; }

dk() {
  if [ "${USE_SUDO:-0}" = "1" ]; then sudo docker "$@"; else docker "$@"; fi
}

if [ "$IN_CONTAINER" = "1" ]; then
  docker info >/dev/null 2>&1 || die "Docker недоступен в контейнере."
else
  if ! command -v docker >/dev/null; then
    warn "Docker не найден."
    if [ "$YES" != "1" ]; then
      read -r -p "Установить Docker? [y/N] " ans </dev/tty 2>/dev/null || ans=n
      case "$ans" in y|Y|yes|YES) ;; *) die "Требуется Docker." ;; esac
    fi
    curl -fsSL https://get.docker.com | sh
    sudo systemctl enable --now docker 2>/dev/null || true
    sudo usermod -aG docker "$USER" 2>/dev/null || true
  fi
  if ! docker info >/dev/null 2>&1; then
    if sudo docker info >/dev/null 2>&1; then
      USE_SUDO=1
    else
      die "Docker недоступен."
    fi
  fi
fi

if [ -d "$APP_DIR" ]; then
  log "Папка $APP_DIR уже есть"
else
  mkdir -p "$APP_DIR"
  log "Создана папка $APP_DIR"
fi

cd "$APP_DIR"

TMP=""
if [ -n "$SOURCE_DIR" ]; then
  log "Используем локальный исходный код: $SOURCE_DIR"
else
  command -v curl >/dev/null || die "Нужен curl."
  TMP="$(mktemp -d)"
  trap '[ -n "$TMP" ] && rm -rf "$TMP"' EXIT
  log "Скачиваем архив с GitHub ($BRANCH)..."
  curl -fsSL "$REPO_URL/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP"
  SOURCE_DIR="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n1)"
fi

# Выбор языка интерфейса
TARGET_LANG="${LANG_CHOICE:-en}"
case "$TARGET_LANG" in en|ru|he) ;; *) warn "Неизвестный язык '$TARGET_LANG', беру en"; TARGET_LANG="en" ;; esac
if [ "$YES" != "1" ] && [ -z "${LANG_CHOICE:-}" ] && { : </dev/tty; } 2>/dev/null; then
  echo "Choose interface language / Выберите язык интерфейса / בחר שפת ממשק:"
  echo "  1) English (en) [default]"
  echo "  2) Русский (ru)"
  echo "  3) עברית (he)"
  user_lang=""
  read -r -p "Enter choice [en/ru/he] (default: en): " user_lang </dev/tty 2>/dev/null || true
  case "$user_lang" in
    ru|RU|2) TARGET_LANG="ru" ;;
    he|HE|3) TARGET_LANG="he" ;;
    *)       TARGET_LANG="en" ;;
  esac
fi

log "Выбран язык интерфейса: $TARGET_LANG"

mkdir -p backend frontend asterisk/sounds
cp -a "$SOURCE_DIR/backend/." ./backend/

# Копируем файлы выбранного языка в корень frontend/ (backend ждёт там index.html)
if [ -f "$SOURCE_DIR/frontend/$TARGET_LANG/index.html" ]; then
  cp -a "$SOURCE_DIR/frontend/$TARGET_LANG/." ./frontend/
  log "Фронтенд ($TARGET_LANG) успешно развернут в плоском виде."
elif [ -f "$SOURCE_DIR/frontend/en/index.html" ]; then
  cp -a "$SOURCE_DIR/frontend/en/." ./frontend/
  warn "Языка $TARGET_LANG нет, используется английский."
elif [ -f "$SOURCE_DIR/frontend/index.html" ]; then
  cp -a "$SOURCE_DIR/frontend/." ./frontend/
  log "Фронтенд (старая плоская раскладка) развернут."
else
  die "В $SOURCE_DIR/frontend не найден index.html"
fi

if [ ! -d asterisk/config ]; then
  cp -a "$SOURCE_DIR/asterisk/config" asterisk/config
  log "Скопированы настройки Asterisk"
fi

if [ -f "$SOURCE_DIR/docker-compose.prod.yml" ]; then
  cp "$SOURCE_DIR/docker-compose.prod.yml" docker-compose.yml
fi
cp "$SOURCE_DIR/.env.example" .env.example

PROJECT="$(basename "$APP_DIR" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n_-' '_')"
VOLUME="${PROJECT}_postgres_data_prod"

if [ "$RESET" = "1" ]; then
  warn "RESET=1: сброс базы данных..."
  dk compose down -v || true
  rm -f .env
fi

if [ ! -f .env ]; then
  if dk volume ls -q | grep -qx "$VOLUME"; then
    die "Обнаружен volume '$VOLUME' без .env. Запустите с RESET=1."
  fi
  cp .env.example .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand)|" .env
  sed -i "s|^AMI_SECRET=.*|AMI_SECRET=$(rand)|" .env
  log "Создан .env со случайными паролями"
else
  log ".env уже существует"
fi

chmod 600 .env
set -a; . ./.env; set +a
case "${POSTGRES_PASSWORD:-}${AMI_SECRET:-}" in
  *CHANGE_ME*|"") die "В .env остались заглушки CHANGE_ME_... - замените их или удалите .env." ;;
esac

MGR="asterisk/config/manager.conf"
[ -f "$MGR" ] || die "Нет файла $MGR"
sed -i "/^\[pbx_api\]/,/^\[/ s|^secret *=.*|secret = ${AMI_SECRET}|" "$MGR"
sed -i "/^\[pbx_api\]/,/^\[/ s|^permit *=.*|permit = 172.16.0.0/255.240.0.0|" "$MGR"
log "AMI secret синхронизирован с .env"

log "Загружаю образы и запускаю..."
dk compose pull --quiet || warn "Не удалось обновить образы из GHCR, используем локальные."
dk compose up -d
dk compose restart backend >/dev/null

log "Ожидание запуска backend (до 60 с)..."
ok=0
for _ in $(seq 1 30); do
  if dk compose exec -T backend python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/', timeout=2)" >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 2
done

if [ "$IN_CONTAINER" = "1" ] && [ -n "${HOST_UID:-}" ]; then
  chown -R "${HOST_UID}:${HOST_GID:-$HOST_UID}" "$APP_DIR" 2>/dev/null || true
fi

dk compose ps

if [ "$ok" = "1" ]; then
  IP="${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
  echo "[OK] Веб-интерфейс доступен: http://${IP:-localhost}:8000"
else
  warn "Backend не ответил вовремя. Проверьте логи: cd $APP_DIR && docker compose logs --tail=50 backend"
  exit 1
fi
