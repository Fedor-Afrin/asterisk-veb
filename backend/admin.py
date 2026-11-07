"""Администрирование: состояние системы, резервная копия и восстановление.

Без новых зависимостей: система читается из /proc, контейнеры - через docker CLI
(сокет Docker уже подключён к backend), архив - стандартный zipfile.
Чистые функции (без базы) вынесены отдельно, чтобы их можно было проверять тестами.
"""
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import zipfile

from sqlalchemy import delete, insert
from sqlalchemy.future import select

import models

SOUNDS_DIR = "/app/sounds"
BACKUP_FORMAT = "asterisk-veb-backup"
BACKUP_VERSION = 1
SETTINGS_NAME = "settings.json"
SOUND_EXTENSIONS = {".wav", ".gsm", ".ulaw", ".alaw", ".sln", ".sln16", ".g722", ".mp3", ".ogg"}
SAFE_SOUND_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MAX_BACKUP_BYTES = 200 * 1024 * 1024          # размер загружаемого архива
MAX_UNPACKED_BYTES = 400 * 1024 * 1024        # защита от zip-бомбы


class BackupError(Exception):
    """Ошибка в файле резервной копии (текст показывается пользователю)."""


# ======================= СОСТОЯНИЕ СИСТЕМЫ =======================

def _read_meminfo(path="/proc/meminfo") -> dict:
    values = {}
    with open(path) as f:
        for line in f:
            key, _, rest = line.partition(":")
            parts = rest.split()
            if parts:
                values[key] = int(parts[0]) * 1024   # kB -> байты
    return values


def system_info(disk_path="/app", proc_dir="/proc") -> dict:
    """Нагрузка, память, диск, время работы. Память, нагрузка и uptime - данные хоста."""
    with open(os.path.join(proc_dir, "loadavg")) as f:
        load = [float(x) for x in f.read().split()[:3]]
    cores = os.cpu_count() or 1

    mem = _read_meminfo(os.path.join(proc_dir, "meminfo"))
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", mem.get("MemFree", 0))
    used = max(total - available, 0)

    usage = shutil.disk_usage(disk_path)

    with open(os.path.join(proc_dir, "uptime")) as f:
        uptime = int(float(f.read().split()[0]))

    return {
        "cpu": {"load": load, "cores": cores, "percent": round(min(load[0] / cores * 100, 100), 1)},
        "memory": {"total": total, "used": used,
                   "percent": round(used / total * 100, 1) if total else 0},
        "disk": {"total": usage.total, "used": usage.used, "free": usage.free,
                 "percent": round(usage.used / usage.total * 100, 1) if usage.total else 0},
        "uptime": uptime,
    }


def _docker(args, timeout=5) -> str:
    result = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker command failed")
    return result.stdout


def containers_info() -> dict:
    """Контейнеры того же compose-проекта, в котором работает backend."""
    try:
        own_id = os.environ.get("HOSTNAME", "")
        project = _docker(["inspect", "-f",
                           '{{ index .Config.Labels "com.docker.compose.project" }}', own_id]).strip()
        if not project:
            return {"containers": [], "error": "compose project not found"}
        out = _docker(["ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
                       "--format", "{{.Names}}\t{{.State}}\t{{.Status}}"])
        containers = []
        for line in out.splitlines():
            name, state, status = (line.split("\t") + ["", "", ""])[:3]
            containers.append({"name": name, "state": state, "status": status})
        containers.sort(key=lambda c: c["name"])
        return {"containers": containers}
    except Exception as exc:
        return {"containers": [], "error": str(exc)}


# ======================= РЕЗЕРВНАЯ КОПИЯ: ЧИСТЫЕ ФУНКЦИИ =======================

def list_sound_files(sounds_dir=SOUNDS_DIR) -> list:
    if not os.path.isdir(sounds_dir):
        return []
    names = []
    for name in sorted(os.listdir(sounds_dir)):
        path = os.path.join(sounds_dir, name)
        if (os.path.isfile(path) and SAFE_SOUND_NAME.match(name)
                and os.path.splitext(name)[1].lower() in SOUND_EXTENSIONS):
            names.append(name)
    return names


def make_backup_zip(settings: dict, sounds_dir=SOUNDS_DIR) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(SETTINGS_NAME, json.dumps(settings, ensure_ascii=False, indent=2))
        for name in list_sound_files(sounds_dir):
            zf.write(os.path.join(sounds_dir, name), f"sounds/{name}")
    return buf.getvalue()


def _check(condition, message):
    if not condition:
        raise BackupError(message)


def validate_settings(data) -> dict:
    """Проверяет структуру и уникальность до того, как что-то будет удалено."""
    _check(isinstance(data, dict) and data.get("format") == BACKUP_FORMAT, "This is not a backup of this PBX")
    _check(data.get("version") == BACKUP_VERSION, "Unsupported backup version")
    for key in ("extensions", "groups", "trunks", "trunk_groups", "ivr_menus"):
        _check(isinstance(data.get(key), list), f"Backup is damaged: no section '{key}'")

    ext_numbers = set()
    for e in data["extensions"]:
        _check(isinstance(e, dict) and isinstance(e.get("extension"), int) and isinstance(e.get("secret"), str),
               "Backup is damaged: bad extension entry")
        _check(e["extension"] not in ext_numbers, f"Duplicate extension {e['extension']} in backup")
        ext_numbers.add(e["extension"])

    trunk_names = set()
    for t in data["trunks"]:
        _check(isinstance(t, dict) and isinstance(t.get("name"), str) and isinstance(t.get("host"), str),
               "Backup is damaged: bad trunk entry")
        _check(t["name"] not in trunk_names, f"Duplicate trunk {t['name']} in backup")
        trunk_names.add(t["name"])

    group_numbers = set()
    for g in data["groups"]:
        _check(isinstance(g, dict) and isinstance(g.get("name"), str) and isinstance(g.get("members"), list),
               "Backup is damaged: bad group entry")
        _check(all(m in ext_numbers for m in g["members"]), f"Group {g['name']} refers to a missing extension")
        if g.get("exten") is not None:
            _check(isinstance(g["exten"], int), "Backup is damaged: bad group number")
            _check(g["exten"] not in group_numbers, f"Group number {g['exten']} is used twice in backup")
            group_numbers.add(g["exten"])

    tg_names = set()
    for tg in data["trunk_groups"]:
        _check(isinstance(tg, dict) and isinstance(tg.get("name"), str) and isinstance(tg.get("trunks"), list),
               "Backup is damaged: bad trunk group entry")
        _check(tg["name"] not in tg_names, f"Duplicate trunk group {tg['name']} in backup")
        tg_names.add(tg["name"])
        _check(all(n in trunk_names for n in tg["trunks"]), f"Trunk group {tg['name']} refers to a missing trunk")

    ivr_names = set()
    ivr_numbers = set()
    for i in data["ivr_menus"]:
        _check(isinstance(i, dict) and isinstance(i.get("name"), str) and isinstance(i.get("extension"), int),
               "Backup is damaged: bad IVR entry")
        _check(i["name"] not in ivr_names, f"Duplicate IVR {i['name']} in backup")
        ivr_names.add(i["name"])
        _check(i["extension"] not in ivr_numbers, f"IVR number {i['extension']} is used twice in backup")
        ivr_numbers.add(i["extension"])
        _check(isinstance(i.get("options") or {}, dict), "Backup is damaged: bad IVR options")
    return data


def read_backup_zip(blob: bytes):
    """Возвращает (настройки, {имя файла: байты}). Бросает BackupError."""
    _check(len(blob) <= MAX_BACKUP_BYTES, "Backup file is too large")
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        raise BackupError("This is not a zip archive")
    with zf:
        infos = zf.infolist()
        _check(sum(i.file_size for i in infos) <= MAX_UNPACKED_BYTES, "Backup file is too large")
        try:
            settings = json.loads(zf.read(SETTINGS_NAME).decode("utf-8"))
        except KeyError:
            raise BackupError("Backup file has no settings.json")
        except (ValueError, UnicodeDecodeError):
            raise BackupError("settings.json is damaged")
        validate_settings(settings)

        sounds = {}
        for info in infos:
            if info.is_dir() or not info.filename.startswith("sounds/"):
                continue
            name = info.filename[len("sounds/"):]
            # только плоские безопасные имена: никаких путей и ../
            if SAFE_SOUND_NAME.match(name) and os.path.splitext(name)[1].lower() in SOUND_EXTENSIONS:
                sounds[name] = zf.read(info)
    return settings, sounds


def write_sounds(sounds: dict, sounds_dir=SOUNDS_DIR) -> int:
    os.makedirs(sounds_dir, exist_ok=True)
    for name, data in sounds.items():
        with open(os.path.join(sounds_dir, name), "wb") as f:
            f.write(data)
    return len(sounds)


# ======================= РЕЗЕРВНАЯ КОПИЯ: БАЗА ДАННЫХ =======================

async def export_settings(db) -> dict:
    extensions = (await db.execute(select(models.Extension).order_by(models.Extension.extension))).scalars().all()
    groups = (await db.execute(select(models.CallGroup).order_by(models.CallGroup.id))).scalars().all()
    trunks = (await db.execute(select(models.Trunk).order_by(models.Trunk.id))).scalars().all()
    trunk_groups = (await db.execute(select(models.TrunkGroup).order_by(models.TrunkGroup.id))).scalars().all()
    ivrs = (await db.execute(select(models.IVRMenu).order_by(models.IVRMenu.id))).scalars().all()
    gm = (await db.execute(select(models.group_members))).all()
    tgm = (await db.execute(select(models.trunk_group_members))).all()

    ext_number = {e.id: e.extension for e in extensions}
    trunk_name = {t.id: t.name for t in trunks}

    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "extensions": [
            {"extension": e.extension, "secret": e.secret, "callerid": e.callerid,
             "transport": e.transport.value if hasattr(e.transport, "value") else str(e.transport)}
            for e in extensions
        ],
        "groups": [
            {"name": g.name, "exten": g.exten, "strategy": g.strategy,
             "members": sorted(ext_number[r.extension_id] for r in gm
                               if r.group_id == g.id and r.extension_id in ext_number)}
            for g in groups
        ],
        "trunks": [
            {"name": t.name, "protocol": t.protocol, "host": t.host,
             "username": t.username, "secret": t.secret}
            for t in trunks
        ],
        "trunk_groups": [
            {"name": tg.name, "strategy": tg.strategy, "prefix": tg.prefix,
             "trunks": [trunk_name[r.trunk_id] for r in tgm
                        if r.group_id == tg.id and r.trunk_id in trunk_name]}
            for tg in trunk_groups
        ],
        "ivr_menus": [
            {"name": i.name, "extension": i.extension, "greeting_file": i.greeting_file,
             "options": i.options or {}}
            for i in ivrs
        ],
    }


async def import_settings(db, data: dict) -> dict:
    """Полностью заменяет настройки АТС содержимым резервной копии (в одной транзакции).

    Пароль администратора и записи разговоров не затрагиваются.
    """
    try:
        # Сначала связи, потом сами таблицы (Core-запросы: без ленивой загрузки ORM)
        await db.execute(delete(models.group_members))
        await db.execute(delete(models.trunk_group_members))
        for model in (models.CallGroup, models.TrunkGroup, models.IVRMenu,
                      models.Extension, models.Trunk):
            await db.execute(delete(model))

        extensions = {}
        for e in data["extensions"]:
            try:
                transport = models.SIPTransport(e.get("transport", models.SIPTransport.UDP.value))
            except ValueError:
                transport = models.SIPTransport.UDP
            obj = models.Extension(extension=e["extension"], secret=e["secret"],
                                   callerid=e.get("callerid"), transport=transport)
            db.add(obj)
            extensions[e["extension"]] = obj

        trunks = {}
        for t in data["trunks"]:
            obj = models.Trunk(name=t["name"], protocol=t.get("protocol", "pjsip"), host=t["host"],
                               username=t.get("username"), secret=t.get("secret"))
            db.add(obj)
            trunks[t["name"]] = obj

        groups = []
        for g in data["groups"]:
            obj = models.CallGroup(name=g["name"], exten=g.get("exten"),
                                   strategy=g.get("strategy", "ring_all"))
            db.add(obj)
            groups.append((obj, g["members"]))

        trunk_groups = []
        for tg in data["trunk_groups"]:
            obj = models.TrunkGroup(name=tg["name"], strategy=tg.get("strategy", "failover"),
                                    prefix=tg.get("prefix", "9"))
            db.add(obj)
            trunk_groups.append((obj, tg["trunks"]))

        for i in data["ivr_menus"]:
            db.add(models.IVRMenu(name=i["name"], extension=i["extension"],
                                  greeting_file=i.get("greeting_file"), options=i.get("options") or {}))

        await db.flush()   # получаем новые id

        links = [{"group_id": obj.id, "extension_id": extensions[n].id}
                 for obj, members in groups for n in members]
        if links:
            await db.execute(insert(models.group_members), links)
        tlinks = [{"group_id": obj.id, "trunk_id": trunks[n].id}
                  for obj, names in trunk_groups for n in names]
        if tlinks:
            await db.execute(insert(models.trunk_group_members), tlinks)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"extensions": len(data["extensions"]), "groups": len(data["groups"]),
            "trunks": len(data["trunks"]), "trunk_groups": len(data["trunk_groups"]),
            "ivr_menus": len(data["ivr_menus"])}
