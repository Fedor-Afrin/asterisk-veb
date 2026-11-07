from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import os
import re
import json
from database import engine, Base, get_db
import models
import schemas
import pbx_config
from ami_client import ami_manager
import subprocess
import asyncio
import datetime
from fastapi import UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete
from database import async_session_maker
import auth
import admin
import recordings
from fastapi.responses import Response

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Asterisk Web Management API", version="2.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ASTERISK_CONFIG_DIR = "/etc/asterisk"

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        await ami_manager.connect()
    except Exception:
        pass

# =========================================================
#                    ВХОД В ВЕБ-ИНТЕРФЕЙС
# =========================================================

class PasswordBody(BaseModel):
    password: str


@app.middleware("http")
async def require_login(request: Request, call_next):
    """Все адреса /api/* (кроме /api/auth/*) доступны только после входа."""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        token = request.cookies.get(auth.COOKIE_NAME)
        allowed = False
        if token:
            async with async_session_maker() as db:
                admin = await auth.get_admin(db)
            allowed = admin is not None and auth.verify_token(admin.session_secret, token)
        if not allowed:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
    return await call_next(request)


def _session_response(admin) -> JSONResponse:
    response = JSONResponse({"status": "success"})
    response.set_cookie(auth.COOKIE_NAME, auth.make_token(admin.session_secret),
                        max_age=auth.SESSION_TTL, httponly=True, samesite="strict", path="/")
    return response


@app.get("/api/auth/status")
async def auth_status(request: Request, db: AsyncSession = Depends(get_db)):
    admin = await auth.get_admin(db)
    token = request.cookies.get(auth.COOKIE_NAME)
    authenticated = bool(admin and token and auth.verify_token(admin.session_secret, token))
    return {"configured": admin is not None, "authenticated": authenticated}


@app.post("/api/auth/setup")
@limiter.limit("10/minute")
async def auth_setup(request: Request, body: PasswordBody, db: AsyncSession = Depends(get_db)):
    """Первый запуск: задать пароль admin. Работает только пока пароль ещё не задан."""
    if await auth.get_admin(db) is not None:
        raise HTTPException(status_code=409, detail="Password is already set")
    error = auth.validate_password(body.password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    try:
        admin = await auth.set_password(db, body.password)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Password is already set")
    return _session_response(admin)


@app.post("/api/auth/login")
@limiter.limit("10/minute")
async def auth_login(request: Request, body: PasswordBody, db: AsyncSession = Depends(get_db)):
    admin = await auth.get_admin(db)
    if admin is None:
        raise HTTPException(status_code=409, detail="Password is not set yet")
    if not await auth.check_password(body.password, admin):
        await asyncio.sleep(1)   # замедляем перебор
        raise HTTPException(status_code=401, detail="Wrong password")
    return _session_response(admin)


@app.post("/api/auth/logout")
async def auth_logout():
    response = JSONResponse({"status": "success"})
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return response


# =========================================================
#                    АДМИНИСТРИРОВАНИЕ
# =========================================================

class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@app.get("/api/admin/system")
async def admin_system():
    info = await asyncio.to_thread(admin.system_info)
    info.update(await asyncio.to_thread(admin.containers_info))
    return info


@app.post("/api/admin/password")
async def admin_change_password(body: ChangePasswordBody, db: AsyncSession = Depends(get_db)):
    current = await auth.get_admin(db)
    # 403, а не 401: 401 интерфейс воспринимает как "сессия истекла"
    if current is None or not await auth.check_password(body.old_password, current):
        await asyncio.sleep(1)
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    error = auth.validate_password(body.new_password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    updated = await auth.set_password(db, body.new_password)   # ключ сессий меняется
    return _session_response(updated)                          # текущая сессия остаётся рабочей


@app.get("/api/admin/backup")
async def admin_backup(db: AsyncSession = Depends(get_db)):
    settings = await admin.export_settings(db)
    blob = await asyncio.to_thread(admin.make_backup_zip, settings)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    return Response(content=blob, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="asterisk-pbx-backup-{stamp}.zip"'})


@app.post("/api/admin/restore")
async def admin_restore(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    blob = await file.read(admin.MAX_BACKUP_BYTES + 1)
    try:
        settings, sounds = admin.read_backup_zip(blob)
    except admin.BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        counts = await admin.import_settings(db, settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Restore failed, current settings were not changed: {exc}")
    counts["sounds"] = await asyncio.to_thread(admin.write_sounds, sounds)

    applied = True
    try:
        await reload_pbx(db)         # пересобрать конфиги и сделать core reload
    except Exception:
        applied = False
    return {"status": "success", "applied": applied, "counts": counts}


# =========================================================
#                    ЗАПИСИ РАЗГОВОРОВ
# =========================================================

class RecordingSettingsBody(BaseModel):
    extensions: list[int]


@app.get("/api/recordings/settings")
async def get_recording_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.RecordingExtension.extension).order_by(models.RecordingExtension.extension))
    return {"extensions": list(result.scalars().all())}


@app.put("/api/recordings/settings")
async def save_recording_settings(body: RecordingSettingsBody, db: AsyncSession = Depends(get_db)):
    """Выбор номеров для записи. Правила попадают в диалплан сразу, а в Asterisk - после "Применить конфигурацию"."""
    known = set((await db.execute(select(models.Extension.extension))).scalars().all())
    chosen = sorted({n for n in body.extensions if n in known})
    await db.execute(delete(models.RecordingExtension))
    for number in chosen:
        db.add(models.RecordingExtension(extension=number))
    await db.commit()
    await regenerate_and_save_configs(db)
    return {"extensions": chosen}


@app.get("/api/recordings")
async def list_recordings(number: str = "", date_from: str = "", date_to: str = "",
                          min_duration: int = 0, limit: int = 50, offset: int = 0,
                          db: AsyncSession = Depends(get_db)):
    await recordings.sync_db(db)
    try:
        total, rows = await recordings.search(db, number.strip() or None, date_from or None,
                                              date_to or None, min_duration or None,
                                              max(1, min(limit, 200)), max(0, offset))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")
    items = []
    for r in rows:
        path = recordings.safe_path(r.filename)
        size = os.path.getsize(path) if path and os.path.isfile(path) else 0
        items.append({"id": r.id, "date": r.date.isoformat() + "Z", "caller": r.caller,
                      "callee": r.callee, "duration": r.duration, "size": size})
    return {"total": total, "items": items}


@app.get("/api/recordings/{rec_id}/audio")
async def recording_audio(rec_id: int, request: Request, download: int = 0,
                          db: AsyncSession = Depends(get_db)):
    rec = await db.get(models.CallRecord, rec_id)
    path = recordings.safe_path(rec.filename) if rec else None
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Recording not found")

    size = os.path.getsize(path)
    headers = {"Accept-Ranges": "bytes"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{rec.filename}"'

    # Поддержка Range: без неё в плеере нельзя перематывать запись
    start, end, partial = 0, size - 1, False
    match = re.match(r"bytes=(\d*)-(\d*)$", request.headers.get("range", ""))
    if match and (match.group(1) or match.group(2)):
        if match.group(1):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
        else:                                    # "bytes=-N": последние N байт
            start = max(size - int(match.group(2)), 0)
        end = min(end, size - 1)
        if start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        partial = True

    with open(path, "rb") as f:
        f.seek(start)
        data = f.read(end - start + 1)
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return Response(content=data, status_code=206 if partial else 200,
                    media_type="audio/wav", headers=headers)


@app.delete("/api/recordings/{rec_id}")
async def delete_recording(rec_id: int, db: AsyncSession = Depends(get_db)):
    rec = await db.get(models.CallRecord, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    path = recordings.safe_path(rec.filename)
    if path and os.path.isfile(path):
        os.remove(path)
    await db.delete(rec)
    await db.commit()
    return {"status": "success"}


FRONTEND_ROOT = "/frontend"


def resolve_ui_dir() -> str:
    """Папка с index.html: /frontend (плоская раскладка) или /frontend/<язык> (папки en/ru/he)."""
    lang = os.getenv("UI_LANG", "").strip()
    candidates = [os.path.join(FRONTEND_ROOT, lang)] if lang else []
    candidates += [FRONTEND_ROOT, os.path.join(FRONTEND_ROOT, "en")]
    for path in candidates:
        if os.path.isfile(os.path.join(path, "index.html")):
            return path
    return FRONTEND_ROOT


UI_DIR = resolve_ui_dir()


@app.get("/")
@limiter.limit("10/minute")
async def read_index(request: Request):
    return FileResponse(os.path.join(UI_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

# =========================================================
#                    УПРАВЛЕНИЕ НОМЕРАМИ
# =========================================================

@app.post("/api/extensions", response_model=schemas.ExtensionResponse, status_code=status.HTTP_201_CREATED)
async def create_extension(ext_data: schemas.ExtensionCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(models.Extension).where(models.Extension.extension == ext_data.extension))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Extension already exists")

    new_ext = models.Extension(
        extension=ext_data.extension,
        secret=ext_data.secret,
        callerid=ext_data.callerid,
        transport=ext_data.transport
    )
    
    db.add(new_ext)
    await db.commit()
    await db.refresh(new_ext)
    await regenerate_and_save_configs(db)
    return new_ext

@app.get("/api/extensions", response_model=list[schemas.ExtensionResponse])
async def get_extensions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Extension).order_by(models.Extension.extension))
    return result.scalars().all()

@app.delete("/api/extensions/{ext_id}", status_code=status.HTTP_200_OK)
async def delete_extension(ext_id: int, db: AsyncSession = Depends(get_db)):
    ext = await db.get(models.Extension, ext_id)
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")
    await db.delete(ext)
    await db.commit()
    await regenerate_and_save_configs(db)
    return {"status": "success"}

@app.put("/api/extensions/{ext_id}", status_code=status.HTTP_200_OK)
async def update_extension(ext_id: int, ext_data: schemas.ExtensionCreate, db: AsyncSession = Depends(get_db)):
    ext = await db.get(models.Extension, ext_id)
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")

    # Если меняем сам номер, проверяем, не занят ли он
    if ext.extension != ext_data.extension:
        existing = await db.execute(select(models.Extension).where(models.Extension.extension == ext_data.extension))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="This extension is already in use")

    ext.extension = ext_data.extension
    ext.secret = ext_data.secret
    ext.callerid = ext_data.callerid
    ext.transport = ext_data.transport

    await db.commit()
    await db.refresh(ext)
    
    # Пересобираем конфиг PJSIP (убедись, что имя твоей функции-генератора совпадает)
    await update_pjsip_config(db) 
    
    return {"status": "success"}

# =========================================================
#                    УПРАВЛЕНИЕ ГРУППАМИ
# =========================================================

@app.post("/api/groups", response_model=schemas.GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(group_data: schemas.GroupCreate, db: AsyncSession = Depends(get_db)):
    # Поддерживаем поле exten из базы
    exten_val = getattr(group_data, 'exten', None)
    
    new_group = models.CallGroup(name=group_data.name, strategy=group_data.strategy)
    if exten_val is not None:
        new_group.exten = exten_val

    for ext_id in group_data.members:
        ext = await db.get(models.Extension, ext_id)
        if ext:
            new_group.members.append(ext)
            
    db.add(new_group)
    await db.commit()
    
    result = await db.execute(select(models.CallGroup).where(models.CallGroup.id == new_group.id).options(selectinload(models.CallGroup.members)))
    new_group = result.scalars().first()
    
    await regenerate_and_save_configs(db) # Обновляем конфиг после создания
    
    return {
        "id": new_group.id, 
        "name": new_group.name, 
        "exten": getattr(new_group, 'exten', None),
        "strategy": new_group.strategy, 
        "members": [m.id for m in new_group.members]
    }

@app.get("/api/groups", response_model=list[schemas.GroupResponse])
async def get_groups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.CallGroup).options(selectinload(models.CallGroup.members)))
    groups = result.scalars().all()
    return [{
        "id": g.id, 
        "name": g.name, 
        "exten": getattr(g, 'exten', None),
        "strategy": g.strategy, 
        "members": [m.id for m in g.members]
    } for g in groups]

@app.put("/api/groups/{group_id}", response_model=schemas.GroupResponse)
async def update_group(group_id: int, group_data: schemas.GroupCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.CallGroup).where(models.CallGroup.id == group_id).options(selectinload(models.CallGroup.members)))
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group.name = group_data.name
    group.strategy = group_data.strategy
    
    # ИСПРАВЛЕНИЕ: Проверка на None вместо True/False
    exten_val = getattr(group_data, 'exten', None)
    if exten_val is not None:
        group.exten = exten_val
    
    group.members = []
    for ext_id in group_data.members:
        ext = await db.get(models.Extension, ext_id)
        if ext:
            group.members.append(ext)
            
    await db.commit()
    await regenerate_and_save_configs(db) # Обновляем конфиг после изменения
    
    return {
        "id": group.id, 
        "name": group.name, 
        "exten": getattr(group, 'exten', None),
        "strategy": group.strategy, 
        "members": [m.id for m in group.members]
    }

@app.delete("/api/groups/{group_id}", status_code=status.HTTP_200_OK)
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.CallGroup).where(models.CallGroup.id == group_id))
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()
    await regenerate_and_save_configs(db) # Обновляем конфиг после удаления
    return {"status": "success"}

# =========================================================
#                    УПРАВЛЕНИЕ ТРАНКАМИ
# =========================================================

@app.post("/api/trunks", response_model=schemas.TrunkResponse, status_code=status.HTTP_201_CREATED)
async def create_trunk(trunk_data: schemas.TrunkCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(models.Trunk).where(models.Trunk.name == trunk_data.name))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="A trunk with this name already exists")

    new_trunk = models.Trunk(**trunk_data.model_dump())
    db.add(new_trunk)
    await db.commit()
    await db.refresh(new_trunk)
    
    await update_trunk_config_files(db)
    return new_trunk

@app.get("/api/trunks", response_model=list[schemas.TrunkResponse])
async def get_trunks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Trunk).order_by(models.Trunk.name))
    return result.scalars().all()

@app.delete("/api/trunks/{trunk_id}", status_code=status.HTTP_200_OK)
async def delete_trunk(trunk_id: int, db: AsyncSession = Depends(get_db)):
    trunk = await db.get(models.Trunk, trunk_id)
    if not trunk:
        raise HTTPException(status_code=404, detail="Trunk not found")
        
    await db.delete(trunk)
    await db.commit()
    
    await update_trunk_config_files(db)
    return {"status": "success"}

@app.put("/api/trunks/{trunk_id}", status_code=status.HTTP_200_OK)
async def update_trunk(trunk_id: int, trunk_data: schemas.TrunkCreate, db: AsyncSession = Depends(get_db)):
    trunk = await db.get(models.Trunk, trunk_id)
    if not trunk:
        raise HTTPException(status_code=404, detail="Trunk not found")
        
    if trunk.name != trunk_data.name:
        existing = await db.execute(select(models.Trunk).where(models.Trunk.name == trunk_data.name))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="A trunk with this name already exists")

    trunk.name = trunk_data.name
    trunk.protocol = trunk_data.protocol
    trunk.host = trunk_data.host
    trunk.username = trunk_data.username
    trunk.secret = trunk_data.secret

    await db.commit()
    # Вызови здесь функции обновления PJSIP/IAX конфигов, которые есть в твоем create_trunk
    # await update_pjsip_config(db)
    # await update_iax_config(db)
    return {"status": "success"}



# =========================================================
#                 УПРАВЛЕНИЕ ТРАНКОВЫМИ ГРУППАМИ
# =========================================================

@app.post("/api/trunk-groups", response_model=schemas.TrunkGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_trunk_group(group_data: schemas.TrunkGroupCreate, db: AsyncSession = Depends(get_db)):
    new_group = models.TrunkGroup(
        name=group_data.name, 
        strategy=group_data.strategy,
        prefix=group_data.prefix
    )
    for t_id in group_data.trunks:
        trk = await db.get(models.Trunk, t_id)
        if trk:
            new_group.trunks.append(trk)
            
    db.add(new_group)
    await db.commit()
    
    await update_trunk_groups_extensions_config(db)
    
    result = await db.execute(
        select(models.TrunkGroup)
        .where(models.TrunkGroup.id == new_group.id)
        .options(selectinload(models.TrunkGroup.trunks))
    )
    g = result.scalars().first()
    return {
        "id": g.id, 
        "name": g.name, 
        "strategy": g.strategy, 
        "prefix": g.prefix,
        "trunks": [t.id for t in g.trunks]
    }

@app.get("/api/trunk-groups", response_model=list[schemas.TrunkGroupResponse])
async def get_trunk_groups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.TrunkGroup).options(selectinload(models.TrunkGroup.trunks)))
    groups = result.scalars().all()
    return [{
        "id": g.id, 
        "name": g.name, 
        "strategy": g.strategy, 
        "prefix": getattr(g, 'prefix', '9'),
        "trunks": [t.id for t in g.trunks]
    } for g in groups]

@app.delete("/api/trunk-groups/{group_id}", status_code=status.HTTP_200_OK)
async def delete_trunk_group(group_id: int, db: AsyncSession = Depends(get_db)):
    group = await db.get(models.TrunkGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Trunk group not found")
    await db.delete(group)
    await db.commit()
    
    await update_trunk_groups_extensions_config(db)
    return {"status": "success"}



@app.put("/api/trunk-groups/{tg_id}", status_code=status.HTTP_200_OK)
async def update_trunk_group(tg_id: int, tg_data: schemas.TrunkGroupCreate, db: AsyncSession = Depends(get_db)):
    tg = await db.get(models.TrunkGroup, tg_id)
    if not tg:
        raise HTTPException(status_code=404, detail="Trunk group not found")

    tg.name = tg_data.name
    tg.strategy = tg_data.strategy
    tg.prefix = tg_data.prefix
    tg.trunks = tg_data.trunks

    await db.commit()
    # Вызови здесь генератор диалплана для транков, который есть в твоем create_trunk_group
    # await update_trunk_extensions_config(db) 
    return {"status": "success"}

# =========================================================
#                    СТАТУСЫ И RELOAD
# =========================================================

@app.get("/api/status")
async def get_pbx_status():
    try:
        if not ami_manager.manager:
            await ami_manager.connect()
            if not ami_manager.manager:
                return {"statuses": {}, "error": "AMI connection is unavailable"}

        response = await ami_manager.manager.send_action({'Action': 'Command', 'Command': 'pjsip show endpoints'})
        
        output_lines = response.output if hasattr(response, 'output') else str(response).splitlines()
        if isinstance(output_lines, str):
            output_lines = output_lines.splitlines()

        statuses = {}
        for line in output_lines:
            line_str = str(line).strip()
            if line_str.startswith("Endpoint:"):
                parts = line_str.split()
                if len(parts) >= 2:
                    ext = parts[1]
                    if ext.startswith("<") or not ext.isdigit():
                        continue
                    state_words = [w for w in parts[2:] if not (w.isdigit() or w == "inf")]
                    statuses[ext] = " ".join(state_words) if state_words else "Unknown"
                    
        return {"statuses": statuses}
    except Exception as e:
        return {"statuses": {}, "error": str(e)}

@app.post("/api/pbx/reload")
async def reload_pbx(db: AsyncSession = Depends(get_db)):
    try:
        # Теперь эта функция пересобирает вообще ВСЁ в строгом порядке
        await regenerate_and_save_configs(db)

        if not ami_manager.manager:
            await ami_manager.connect()
            if not ami_manager.manager:
                raise HTTPException(status_code=500, detail="AMI connection is unavailable")
                
        await ami_manager.manager.send_action({'Action': 'Command', 'Command': 'core reload'})
        return {"status": "success", "message": "Configuration successfully applied to Asterisk!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
#         ГЕНЕРАТОРЫ КОНФИГУРАЦИЙ
# =========================================================

async def regenerate_and_save_configs(db: AsyncSession):
    """
    Собирает все конфиги в строгом порядке, 
    чтобы не затирать IVR и Транковые маршруты!
    """
    # 1. Собираем номера
    result_ext = await db.execute(select(models.Extension))
    extensions = result_ext.scalars().all()
    ext_data = [
        {
            "id": e.id,
            "extension": e.extension,
            "secret": e.secret,
            "callerid": e.callerid,
            "transport": e.transport.value if hasattr(e.transport, "value") else str(e.transport)
        }
        for e in extensions
    ]

    # 2. Собираем группы
    result_grp = await db.execute(select(models.CallGroup).options(selectinload(models.CallGroup.members)))
    groups = result_grp.scalars().all()
    
    groups_data = [
        {
            "id": g.id,
            "name": g.name,
            "exten": getattr(g, "exten", "600"), 
            "strategy": g.strategy,
            "members": [m.id for m in g.members]
        }
        for g in groups
    ]

    # 3. Базовая генерация (ВНИМАНИЕ: ЭТОТ ШАГ ОЧИЩАЕТ ФАЙЛ EXTENSIONS)
    result_rec = await db.execute(select(models.RecordingExtension.extension))
    recording_exts = [row for row in result_rec.scalars().all()]
    os.makedirs(recordings.RECORDINGS_DIR, exist_ok=True)   # общая папка backend/Asterisk

    success_pjp, err_pjp = pbx_config.save_pjsip_config(ext_data)
    success_ext, err_ext = pbx_config.save_extensions_config(ext_data, groups_data, recording_exts)

    # 4. ДОПИСЫВАЕМ ОСТАЛЬНОЕ (ЭТО СПАСАЕТ IVR И ТРАНКИ ОТ УДАЛЕНИЯ)
    await update_trunk_config_files(db)
    await update_trunk_groups_extensions_config(db)
    await update_ivr_extensions_config(db)

async def update_trunk_config_files(db: AsyncSession):
    """Вспомогательная функция для записи файлов конфигурации транков"""
    result = await db.execute(select(models.Trunk))
    trunks = result.scalars().all()
    
    pjsip_trunks_text = "\n; ==========================================\n"
    pjsip_trunks_text += "; Auto-generated PJSIP Trunks configuration\n"
    pjsip_trunks_text += "; ==========================================\n\n"
    
    iax_trunks_text = "\n; ==========================================\n"
    iax_trunks_text += "; Auto-generated IAX2 Trunks configuration\n"
    iax_trunks_text += "; ==========================================\n\n"
    
    for trunk in trunks:
        if trunk.protocol.lower() == "pjsip":
            if trunk.username and trunk.secret:
                pjsip_trunks_text += f"[{trunk.name}_reg]\n"
                pjsip_trunks_text += "type=registration\n"
                pjsip_trunks_text += f"outbound_auth={trunk.name}_auth\n"
                pjsip_trunks_text += f"server_uri=sip:{trunk.host}\n"
                pjsip_trunks_text += f"client_uri=sip:{trunk.username}@{trunk.host}\n"
                pjsip_trunks_text += "retry_interval=60\n\n"

                pjsip_trunks_text += f"[{trunk.name}_auth]\n"
                pjsip_trunks_text += "type=auth\n"
                pjsip_trunks_text += "auth_type=userpass\n"
                pjsip_trunks_text += f"password={trunk.secret}\n"
                pjsip_trunks_text += f"username={trunk.username}\n\n"

            pjsip_trunks_text += f"[{trunk.name}]\n"
            pjsip_trunks_text += "type=aor\n"
            pjsip_trunks_text += f"contact=sip:{trunk.host}\n\n"

            pjsip_trunks_text += f"[{trunk.name}]\n"
            pjsip_trunks_text += "type=endpoint\n"
            pjsip_trunks_text += "context=from-external\n"
            pjsip_trunks_text += "disallow=all\n"
            pjsip_trunks_text += "allow=alaw,ulaw\n"
            if trunk.username and trunk.secret:
                pjsip_trunks_text += f"outbound_auth={trunk.name}_auth\n"
            pjsip_trunks_text += f"aors={trunk.name}\n\n"

            pjsip_trunks_text += f"[{trunk.name}_identify]\n"
            pjsip_trunks_text += "type=identify\n"
            pjsip_trunks_text += f"endpoint={trunk.name}\n"
            pjsip_trunks_text += f"match={trunk.host}\n\n"
            
        elif trunk.protocol.lower() == "iax2":
            iax_trunks_text += f"[{trunk.name}]\n"
            iax_trunks_text += "type=friend\n"
            iax_trunks_text += f"host={trunk.host}\n"
            if trunk.username:
                iax_trunks_text += f"username={trunk.username}\n"
            if trunk.secret:
                iax_trunks_text += f"secret={trunk.secret}\n"
            iax_trunks_text += "context=from-external\n"
            iax_trunks_text += "trunk=yes\n"
            iax_trunks_text += "requirecalltoken=no\n\n"

    pjsip_path = os.path.join(ASTERISK_CONFIG_DIR, "pjsip_users.conf")
    if os.path.exists(pjsip_path):
        with open(pjsip_path, "r", encoding="utf-8") as f:
            content = f.read()
            split_marker = "; ==========================================\n; Auto-generated PJSIP Trunks configuration"
            if split_marker in content:
                content = content.split(split_marker)[0]
        
        with open(pjsip_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n\n" + pjsip_trunks_text)

    iax_path = os.path.join(ASTERISK_CONFIG_DIR, "iax.conf")
    if os.path.exists(iax_path):
        with open(iax_path, "r", encoding="utf-8") as f:
            iax_content = f.read()
            iax_split_marker = "; ==========================================\n; Auto-generated IAX2 Trunks configuration"
            if iax_split_marker in iax_content:
                iax_content = iax_content.split(iax_split_marker)[0]
                
        with open(iax_path, "w", encoding="utf-8") as f:
            f.write(iax_content.strip() + "\n\n" + iax_trunks_text)

async def update_trunk_groups_extensions_config(db: AsyncSession):
    """Генерация правил набора в extensions_users.conf на основе транковых групп"""
    result = await db.execute(
        select(models.TrunkGroup)
        .options(selectinload(models.TrunkGroup.trunks))
    )
    groups = result.scalars().all()

    routes_text = "\n; ==========================================\n"
    routes_text += "; Auto-generated Outbound Routes (Trunk Groups)\n"
    routes_text += "; ==========================================\n\n"

    for g in groups:
        if not g.trunks:
            continue
            
        prefix = g.prefix if hasattr(g, 'prefix') and g.prefix else "9"
        
        routes_text += f"; --- Trunk Group: {g.name} (Prefix: {prefix}) ---\n"
        routes_text += f"exten => _{prefix}X.,1,NoOp(Outbound call via Trunk Group {g.name})\n"
        
        dial_strings = []
        for t in g.trunks:
            if t.protocol.lower() == "pjsip":
                dial_strings.append(f"PJSIP/${{EXTEN:{len(prefix)}}}@{t.name}")
            elif t.protocol.lower() == "iax2":
                dial_strings.append(f"IAX2/{t.name}/${{EXTEN:{len(prefix)}}}")
        
        dial_cmd = "&".join(dial_strings)
        routes_text += f"same => n,Dial({dial_cmd},60,{pbx_config.rec_option('${EXTEN:' + str(len(prefix)) + '}')})\n"
        routes_text += "same => n,Hangup()\n\n"

    ext_path = os.path.join(ASTERISK_CONFIG_DIR, "extensions_users.conf")
    if os.path.exists(ext_path):
        with open(ext_path, "r", encoding="utf-8") as f:
            content = f.read()
            marker = "; ==========================================\n; Auto-generated Outbound Routes"
            if marker in content:
                content = content.split(marker)[0]
        
        with open(ext_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n\n" + routes_text)

async def update_ivr_extensions_config(db: AsyncSession):
    """Генерация диалплана для голосовых меню (IVR)"""
    result = await db.execute(select(models.IVRMenu))
    ivrs = result.scalars().all()

    ivr_text = "\n; ==========================================\n"
    ivr_text += "; Auto-generated IVR Menus\n"
    ivr_text += "; ==========================================\n\n"

    # ВАЖНО: Мы вынесли этот блок из-под условия "if ivrs:", 
    # чтобы контекст и сервисный номер *77 создавались ВСЕГДА!
    ivr_text += "[ivr_menus]\n"
    ivr_text += "; --- Сервисный код для записи IVR с телефона ---\n"
    ivr_text += "exten => _*77X.,1,Answer()\n"
    ivr_text += "same => n,Wait(1)\n"
    ivr_text += "same => n,Playback(beep)\n"
    ivr_text += "same => n,Record(custom/ivr_${EXTEN:3}.wav)\n"
    ivr_text += "same => n,Wait(1)\n"
    ivr_text += "same => n,Playback(custom/ivr_${EXTEN:3})\n"
    ivr_text += "same => n,Hangup()\n\n"

    if ivrs:
        for i in ivrs:
            ivr_text += f"exten => {i.extension},1,Goto(ivr-{i.extension},s,1)\n"
        ivr_text += "\n"

        for i in ivrs:
            ivr_text += f"[ivr-{i.extension}]\n"
            audio = i.greeting_file if i.greeting_file else "beep"
            ivr_text += f"exten => s,1,NoOp(IVR {i.name})\n"
            ivr_text += f"same => n,Answer()\n"
            ivr_text += f"same => n,Background({audio})\n"
            ivr_text += f"same => n,WaitExten(5)\n\n"

            options = i.options
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except:
                    options = {}
            options = options or {}

            for digit, action in options.items():
                target = action.get('target', '')
                action_type = action.get('type')

                if action_type == 'extension':
                    ivr_text += f"exten => {digit},1,Dial(PJSIP/{target},30,{pbx_config.rec_option(target)})\n"
                elif action_type == 'group':
                    ivr_text += f"exten => {digit},1,Goto(groups,{target},1)\n"
                elif action_type == 'ivr':
                    ivr_text += f"exten => {digit},1,Goto(ivr-{target},s,1)\n"
                elif action_type == 'hangup':
                    ivr_text += f"exten => {digit},1,Hangup()\n"

            if 'i' not in options:
                ivr_text += f"exten => i,1,Playback(pbx-invalid)\n"
                ivr_text += f"same => n,Goto(s,1)\n"

            if 't' not in options:
                ivr_text += f"exten => t,1,Hangup()\n"

            ivr_text += "\n"

    ext_path = os.path.join(ASTERISK_CONFIG_DIR, "extensions_users.conf")
    if os.path.exists(ext_path):
        with open(ext_path, "r", encoding="utf-8") as f:
            content = f.read()

        marker_ivr = "; ==========================================\n; Auto-generated IVR Menus"
        if marker_ivr in content:
            content = content.split(marker_ivr)[0].strip()

        with open(ext_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n\n" + ivr_text)     

# =========================================================
#                    УПРАВЛЕНИЕ IVR
# =========================================================

@app.post("/api/ivr", response_model=schemas.IVRResponse, status_code=status.HTTP_201_CREATED)
async def create_ivr(ivr_data: schemas.IVRCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(models.IVRMenu).where(models.IVRMenu.extension == ivr_data.extension))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="This extension number is already in use")

    new_ivr = models.IVRMenu(**ivr_data.model_dump())
    db.add(new_ivr)
    await db.commit()
    await db.refresh(new_ivr)
    
    await update_ivr_extensions_config(db)
    
    # Защита от возврата JSON в виде строки (особенность asyncpg)
    opts = new_ivr.options
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except:
            opts = {}
            
    return {
        "id": new_ivr.id,
        "name": new_ivr.name,
        "extension": new_ivr.extension,
        "greeting_file": new_ivr.greeting_file,
        "options": opts or {}
    }


@app.put("/api/ivr/{ivr_id}", response_model=schemas.IVRResponse)
async def update_ivr(ivr_id: int, ivr_data: schemas.IVRCreate, db: AsyncSession = Depends(get_db)):
    ivr = await db.get(models.IVRMenu, ivr_id)
    if not ivr:
        raise HTTPException(status_code=404, detail="IVR menu not found")
    
    # Проверяем, не занят ли новый номер (если номер изменился)
    if ivr.extension != ivr_data.extension:
        existing = await db.execute(select(models.IVRMenu).where(models.IVRMenu.extension == ivr_data.extension))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="This extension number is already in use")
            
    ivr.name = ivr_data.name
    ivr.extension = ivr_data.extension
    ivr.greeting_file = ivr_data.greeting_file
    ivr.options = ivr_data.options
    
    await db.commit()
    await db.refresh(ivr)
    await update_ivr_extensions_config(db)
    
    opts = ivr.options
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except:
            opts = {}
            
    return {
        "id": ivr.id,
        "name": ivr.name,
        "extension": ivr.extension,
        "greeting_file": ivr.greeting_file,
        "options": opts or {}
    }

@app.get("/api/ivr", response_model=list[schemas.IVRResponse])
async def get_ivrs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.IVRMenu))
    ivrs = result.scalars().all()
    
    # Собираем ответ вручную, чтобы безопасно распарсить JSON
    res = []
    for i in ivrs:
        opts = i.options
        if isinstance(opts, str):
            try:
                opts = json.loads(opts)
            except:
                opts = {}
        res.append({
            "id": i.id,
            "name": i.name,
            "extension": i.extension,
            "greeting_file": i.greeting_file,
            "options": opts or {}
        })
    return res

@app.delete("/api/ivr/{ivr_id}", status_code=status.HTTP_200_OK)
async def delete_ivr(ivr_id: int, db: AsyncSession = Depends(get_db)):
    ivr = await db.get(models.IVRMenu, ivr_id)
    if not ivr:
        raise HTTPException(status_code=404, detail="IVR menu not found")
    await db.delete(ivr)
    await db.commit()
    await update_ivr_extensions_config(db)
    return {"status": "success"}      


@app.post("/api/audio/upload")
async def upload_audio(file: UploadFile = File(...)):
    os.makedirs("/app/sounds", exist_ok=True)
    
    # Достаем имя файла без расширения (например, "music" из "music.mp3")
    filename_without_ext = os.path.splitext(file.filename)[0]
    temp_path = f"/tmp/{file.filename}"
    final_wav = f"/app/sounds/{filename_without_ext}.wav"

    # Сохраняем то, что загрузил пользователь
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())

    # Конвертируем в формат Asterisk (WAV, 8000Hz, Mono, 16-bit PCM) с помощью ffmpeg
    cmd = [
        "ffmpeg", "-y", "-i", temp_path,
        "-ar", "8000", "-ac", "1", "-c:a", "pcm_s16le", final_wav
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if os.path.exists(temp_path):
        os.remove(temp_path)

    # Возвращаем путь, который нужно вставить в диалплан
    return {"status": "success", "file": f"custom/{filename_without_ext}"}