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

from database import engine, Base, get_db
import models
import schemas
import pbx_config
from ami_client import ami_manager

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

@app.get("/")
@limiter.limit("10/minute")
async def read_index(request: Request):
    return FileResponse("/frontend/index.html")

app.mount("/static", StaticFiles(directory="/frontend"), name="static")

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
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
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
        raise HTTPException(status_code=404, detail="Группа не найдена")

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
        raise HTTPException(status_code=400, detail="Транк с таким именем уже существует")

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
        raise HTTPException(status_code=404, detail="Транк не найден")
        
    await db.delete(trunk)
    await db.commit()
    
    await update_trunk_config_files(db)
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
        raise HTTPException(status_code=404, detail="Транковая группа не найдена")
    await db.delete(group)
    await db.commit()
    
    await update_trunk_groups_extensions_config(db)
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
                return {"statuses": {}, "error": "Нет подключения к AMI"}

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
        # ПРИНУДИТЕЛЬНО регенерируем все конфиги перед релоадом
        await regenerate_and_save_configs(db)
        await update_trunk_config_files(db)
        await update_trunk_groups_extensions_config(db)

        if not ami_manager.manager:
            await ami_manager.connect()
            if not ami_manager.manager:
                raise HTTPException(status_code=500, detail="Нет подключения к AMI")
                
        await ami_manager.manager.send_action({'Action': 'Command', 'Command': 'core reload'})
        return {"status": "success", "message": "Конфигурация успешно применена в Asterisk!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
#         ГЕНЕРАТОРЫ КОНФИГУРАЦИЙ
# =========================================================

async def regenerate_and_save_configs(db: AsyncSession):
    """Вспомогательная функция для сборки конфигов из БД для номеров и групп"""
    # 1. Запрашиваем номера
    result_ext = await db.execute(select(models.Extension))
    extensions = result_ext.scalars().all()

    ext_data = [
        {
            "id": e.id,  # <-- ВАЖНО: Добавили ID для сопоставления внутри функции групп
            "extension": e.extension,
            "secret": e.secret,
            "callerid": e.callerid,
            "transport": e.transport.value if hasattr(e.transport, "value") else str(e.transport)
        }
        for e in extensions
    ]

    # 2. Запрашиваем группы
    result_grp = await db.execute(select(models.CallGroup).options(selectinload(models.CallGroup.members)))
    groups = result_grp.scalars().all()
    
    groups_data = [
        {
            "id": g.id,
            "name": g.name,
            "exten": getattr(g, "exten", "600"), # Подхватываем exten из базы
            "strategy": g.strategy,
            "members": [m.id for m in g.members]
        }
        for g in groups
    ]

    # 3. Сохраняем файлы (передаем оба списка!)
    success_pjp, err_pjp = pbx_config.save_pjsip_config(ext_data)
    success_ext, err_ext = pbx_config.save_extensions_config(ext_data, groups_data)

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
        routes_text += f"same => n,Dial({dial_cmd}, 60)\n"
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