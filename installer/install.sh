#!/usr/bin/env bash
# Asterisk Web PBX - полное развёртывание одной командой.
#
# Вариант 1. Bash-скрипт на хосте (сам поставит Docker, если его нет):
#   curl -fsSL https://raw.githubusercontent.com/Fedor-Afrin/asterisk-veb/main/installer/install.sh | bash
#
# Вариант 2. Контейнер-установщик (Docker уже стоит):
#   mkdir -p ~/asterisk-pbx
#   docker run --rm -it \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -v ~/asterisk-pbx:$HOME/asterisk-pbx -e APP_DIR=$HOME/asterisk-pbx \
#     -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
#     ghcr.io/fedor-afrin/asterisk-veb-installer:latest
#
# Переменные окружения:
#   APP_DIR=/opt/asterisk-pbx   куда ставить (по умолчанию ~/asterisk-pbx; в контейнере обязательна)
#   BRANCH=main                 ветка для загрузки
#   SOURCE_DIR=/путь/к/клону    брать файлы из локальной папки, не скачивать
#   RESET=1                     удалить старую базу (volume) и начать с чистой
#   YES=1                       не спрашивать подтверждение установки Docker
#
# Скрипт идемпотентный: повторный запуск ничего не ломает.
#   - папка есть -> не создаётся заново
#   - .env есть  -> пароли НЕ перегенерируются (иначе не совпадут с базой)
#   - asterisk/config уже есть -> не перезаписывается (там ваши номера и транки)
set -euo pipefail

IN_CONTAINER="${IN_INSTALLER_CONTAINER:-0}"
BRANCH="${BRANCH:-main}"
REPO_URL="https://github.com/Fedor-Afrin/asterisk-veb"
SOURCE_DIR="${SOURCE_DIR:-}"
RESET="${RESET:-0}"
YES="${YES:-0}"

if [ "$IN_CONTAINER" = "1" ]; then
  # Внутри контейнера путь ОБЯЗАН совпадать с путём на хосте: compose передаёт
  # bind-mount'ы (./backend и т.д.) Docker-демону, а тот ищет их на хосте.
  [ -n "${APP_DIR:-}" ] || { echo "[!] В контейнере нужен -e APP_DIR=<тот же путь, что смонтирован -v>" >&2; exit 1; }
else
  APP_DIR="${APP_DIR:-$HOME/asterisk-pbx}"
fi

# Запуск из клона репозитория (./installer/install.sh): берём файлы оттуда, а не из сети
if [ -z "$SOURCE_DIR" ] && [ "$IN_CONTAINER" != "1" ] && [ -f "${BASH_SOURCE[0]:-}" ]; then
  _here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [ -d "$_here/backend" ] && [ -f "$_here/docker-compose.prod.yml" ] && [ -f "$_here/.env.example" ]; then
    SOURCE_DIR="$_here"
  fi
fi

log()  { echo "[*] $*"; }
warn() { echo "[!] $*" >&2; }
die()  { warn "$*"; exit 1; }

# Случайный секрет из /dev/urandom (48 hex-символов), без внешних зависимостей
rand() { LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 48; }

# docker с автоматическим sudo, если текущий пользователь ещё не в группе docker
dk() {
  if [ "${USE_SUDO:-0}" = "1" ]; then sudo docker "$@"; else docker "$@"; fi
}

# --- 0. Docker ---------------------------------------------------------------
if [ "$IN_CONTAINER" = "1" ]; then
  docker info >/dev/null 2>&1 || die "Нет доступа к Docker. Добавьте -v /var/run/docker.sock:/var/run/docker.sock"
else
  if ! command -v docker >/dev/null; then
    warn "Docker не найден."
    if [ "$YES" != "1" ]; then
      read -r -p "Установить Docker через официальный скрипт get.docker.com (нужен sudo)? [y/N] " ans </dev/tty 2>/dev/null || ans=n
      case "$ans" in y|Y|yes|YES) ;; *) die "Без Docker продолжать нельзя." ;; esac
    fi
    command -v curl >/dev/null || die "Нужен curl для установки Docker."
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl enable --now docker 2>/dev/null || true
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    log "Docker установлен. Чтобы работать без sudo, перелогиньтесь (группа docker)."
  fi
  if ! docker info >/dev/null 2>&1; then
    if sudo docker info >/dev/null 2>&1; then
      USE_SUDO=1; log "Текущий пользователь не в группе docker - использую sudo для этого запуска"
    else
      die "Docker не отвечает. Проверьте: sudo systemctl status docker"
    fi
  fi
  dk compose version >/dev/null 2>&1 || die "Нужен плагин 'docker compose' (v2): https://docs.docker.com/compose/install/linux/"
fi

# --- 1. Папка ----------------------------------------------------------------
if [ -d "$APP_DIR" ]; then
  log "Папка $APP_DIR уже есть"
else
  mkdir -p "$APP_DIR"
  log "Создана папка $APP_DIR"
fi
cd "$APP_DIR"

# --- 2. Файлы проекта --------------------------------------------------------
TMP=""
if [ -n "$SOURCE_DIR" ]; then
  log "Беру файлы проекта из $SOURCE_DIR"
else
  command -v curl >/dev/null || die "Нужен curl."
  TMP="$(mktemp -d)"
  trap '[ -n "$TMP" ] && rm -rf "$TMP"' EXIT
  log "Скачиваю $REPO_URL ($BRANCH)"
  curl -fsSL "$REPO_URL/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP"
  SOURCE_DIR="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n1)"
fi

# Код обновляем всегда. Копируем "внутрь" папок, не удаляя их:
# они примонтированы в контейнеры, и пересоздание папки сломало бы mount.
mkdir -p backend frontend asterisk/sounds
cp -a "$SOURCE_DIR/backend/."  ./backend/

# --- LANGUAGE SELECTION & FRONTEND DEPLOYMENT ---
TARGET_LANG="${LANG_CHOICE:-en}"
if [ "$YES" != "1" ] && [ -z "${LANG_CHOICE:-}" ]; then
  echo "Choose interface language / Выберите язык интерфейса / בחר שפת ממשק:"
  echo "  1) English (en) [default]"
  echo "  2) Русский (ru)"
  echo "  3) עברית (he)"
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

if [ -d "$SOURCE_DIR/frontend/$TARGET_LANG" ]; then
  cp -a "$SOURCE_DIR/frontend/$TARGET_LANG/." ./frontend/
  log "Фронтенд ($TARGET_LANG) успешно развернут."
else
  cp -a "$SOURCE_DIR/frontend/en/." ./frontend/
  warn "Языковая папка $TARGET_LANG не найдена, используется английский по умолчанию."
fi

 Настройки Asterisk копируем только если их ещё нет (там живут ваши номера/транки)
if [ ! -d asterisk/config ]; then
  cp -a "$SOURCE_DIR/asterisk/config" asterisk/config
  log "Скопированы настройки Asterisk"
fi
# Compose-файл: prod-вариант с готовыми образами
if [ -f "$SOURCE_DIR/docker-compose.prod.yml" ]; then
  cp "$SOURCE_DIR/docker-compose.prod.yml" docker-compose.yml
fi
cp "$SOURCE_DIR/.env.example" .env.example

# --- 3. Старая база с другим паролем? ----------------------------------------
PROJECT="$(basename "$APP_DIR" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n_-' '_')"
VOLUME="${PROJECT}_postgres_data_prod"

if [ "$RESET" = "1" ]; then
  warn "RESET=1: удаляю контейнеры и базу"
  dk compose down -v || true
  rm -f .env
fi

# --- 4. .env -----------------------------------------------------------------
if [ ! -f .env ]; then
  if dk volume ls -q | grep -qx "$VOLUME"; then
    die "Найден старый volume '$VOLUME' с базой, а .env нет: новый пароль не подойдёт к старой базе.
    Если данные не нужны, запустите с RESET=1 (для контейнера: -e RESET=1).
    Если нужны, создайте .env вручную со старым POSTGRES_PASSWORD."
  fi
  cp .env.example .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand)|" .env
  sed -i "s|^AMI_SECRET=.*|AMI_SECRET=$(rand)|" .env
  log "Создан .env со случайными паролями"
else
  log ".env уже есть - пароли не меняю"
fi
chmod 600 .env

set -a; . ./.env; set +a
case "${POSTGRES_PASSWORD:-}${AMI_SECRET:-}" in
  *CHANGE_ME*|"") die "В .env остались заглушки CHANGE_ME_... - замените их или удалите .env." ;;
esac

# --- 5. AMI secret в manager.conf всегда равен AMI_SECRET из .env ------------
MGR="asterisk/config/manager.conf"
[ -f "$MGR" ] || die "Нет $MGR"
sed -i "/^\[pbx_api\]/,/^\[/ s|^secret *=.*|secret = ${AMI_SECRET}|" "$MGR"
# Backend ходит из compose-сети (172.16-31.x.x), а не только из docker0 (172.17)
sed -i "/^\[pbx_api\]/,/^\[/ s|^permit *=.*|permit = 172.16.0.0/255.240.0.0|" "$MGR"
log "AMI secret синхронизирован с .env"

# --- 6. Запуск ---------------------------------------------------------------
log "Загружаю образы и запускаю"
dk compose pull --quiet || warn "pull не удался (образы приватные? пакеты GHCR должны быть public), использую локальные"
dk compose up -d
dk compose restart backend >/dev/null   # подхватить обновлённый код/секрет

# --- 7. Ожидание backend (проверка изнутри контейнера: работает в обоих режимах)
log "Жду backend (до 60 с)"
ok=0
for _ in $(seq 1 30); do
  if dk compose exec -T backend python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/', timeout=2)" >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 2
done

# Файлы должны принадлежать пользователю, а не root (актуально для контейнера)
if [ "$IN_CONTAINER" = "1" ] && [ -n "${HOST_UID:-}" ]; then
  chown -R "${HOST_UID}:${HOST_GID:-$HOST_UID}" "$APP_DIR" 2>/dev/null || true
fi

echo
dk compose ps
echo
if [ "$ok" = "1" ]; then
  IP="${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
  echo "[OK] Веб-интерфейс: http://${IP:-<адрес-этого-компьютера>}:8000"
else
  warn "Backend не ответил. Логи: cd $APP_DIR && docker compose logs --tail=50 backend"
  exit 1
fi
echo "SIP: UDP 5060, RTP: UDP 10000-20000, IAX2: UDP 4569, AMI: TCP 5038 (только docker-сети)"
