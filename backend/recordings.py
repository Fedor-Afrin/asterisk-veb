"""Записи разговоров.

Asterisk (MixMonitor) кладёт файлы в общую папку, backend их только читает:
во время звонка ни база, ни backend не нужны. Метаданные попадают в базу, когда
открывают вкладку (синхронизация папки), поэтому фильтры работают быстро.

Имя файла: ГГГГММДД-ЧЧММСС_звонящий_ответивший_uniqueid.wav (время UTC).
"""
import asyncio
import datetime
import os
import re
import time
import wave

from sqlalchemy import delete, func
from sqlalchemy.future import select

import models

RECORDINGS_DIR = "/app/sounds/recordings"
NAME_RE = re.compile(r"^(\d{8})-(\d{6})_([^_]*)_([^_]*)_([A-Za-z0-9.\-]+)\.wav$")
SETTLE_SECONDS = 15        # файл, который пишется прямо сейчас, пропускаем
_sync_lock = asyncio.Lock()   # два одновременных запроса не должны добавить одну запись дважды


def parse_filename(name: str):
    """Возвращает (время UTC, звонящий, ответивший) или None, если имя не наше."""
    match = NAME_RE.match(name)
    if not match:
        return None
    try:
        when = datetime.datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return when, match.group(3), match.group(4)


def wav_duration(path: str):
    """Длительность в секундах или None, если файл ещё не закончен/повреждён."""
    try:
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            return int(round(w.getnframes() / rate)) if rate else None
    except (wave.Error, EOFError, OSError):
        return None


def scan_folder(directory=RECORDINGS_DIR, now=None):
    """Готовые записи в папке: {имя файла: (время, звонящий, ответивший, секунд)}."""
    found = {}
    if not os.path.isdir(directory):
        return found
    now = time.time() if now is None else now
    for name in os.listdir(directory):
        parsed = parse_filename(name)
        path = os.path.join(directory, name)
        if not parsed or not os.path.isfile(path):
            continue
        if now - os.path.getmtime(path) < SETTLE_SECONDS:
            continue
        duration = wav_duration(path)
        if duration is None:
            continue
        found[name] = parsed + (duration,)
    return found


def safe_path(filename: str, directory=RECORDINGS_DIR):
    """Путь к файлу записи или None, если имя подозрительное."""
    if not filename or filename != os.path.basename(filename) or not NAME_RE.match(filename):
        return None
    return os.path.join(directory, filename)


async def sync_db(db, directory=RECORDINGS_DIR):
    """Добавляет новые файлы в базу и убирает записи, чьих файлов уже нет."""
    async with _sync_lock:
        await _sync_db(db, directory)


async def _sync_db(db, directory):
    on_disk = scan_folder(directory)
    known = {row.filename: row.id for row in
             (await db.execute(select(models.CallRecord.filename, models.CallRecord.id))).all()}

    for name, (when, caller, callee, seconds) in on_disk.items():
        if name not in known:
            db.add(models.CallRecord(date=when, caller=caller, callee=callee,
                                     duration=seconds, filename=name))
    existing_names = set(os.listdir(directory)) if os.path.isdir(directory) else set()
    gone = [rid for name, rid in known.items() if name not in existing_names]
    if gone:
        await db.execute(delete(models.CallRecord).where(models.CallRecord.id.in_(gone)))
    await db.commit()


async def search(db, number=None, date_from=None, date_to=None, min_duration=None,
                 limit=50, offset=0):
    """Список записей с фильтрами. Даты - календарные дни (UTC) в формате ГГГГ-ММ-ДД."""
    conditions = []
    if number:
        conditions.append((models.CallRecord.caller == number) | (models.CallRecord.callee == number))
    if date_from:
        conditions.append(models.CallRecord.date >= datetime.datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        conditions.append(models.CallRecord.date < datetime.datetime.strptime(date_to, "%Y-%m-%d")
                          + datetime.timedelta(days=1))
    if min_duration:
        conditions.append(models.CallRecord.duration >= min_duration)

    total = (await db.execute(select(func.count()).select_from(models.CallRecord)
                              .where(*conditions))).scalar() or 0
    rows = (await db.execute(select(models.CallRecord).where(*conditions)
                             .order_by(models.CallRecord.date.desc(), models.CallRecord.id.desc())
                             .limit(limit).offset(offset))).scalars().all()
    return total, rows
