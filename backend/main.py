from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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

async def regenerate_and_save_configs(db: AsyncSession):
    """Вспомогательная функция для сборки конфигов из БД"""
    result = await db.execute(select(models.Extension))
    extensions = result.scalars().all()

    ext_data = [
        {
            "extension": e.extension,
            "secret": e.secret,
            "callerid": e.callerid,
            "transport": e.transport.value if hasattr(e.transport, "value") else str(e.transport)
        }
        for e in extensions
    ]

    print(f"DEBUG EXTS DATA: {ext_data}")

    success_pjp, err_pjp = pbx_config.save_pjsip_config(ext_data)
    print(f"PJSIP save result: {success_pjp}, path/err: {err_pjp}")

    success_ext, err_ext = pbx_config.save_extensions_config(ext_data)
    print(f"Extensions save result: {success_ext}, path/err: {err_ext}")

@app.post("/api/extensions", response_model=schemas.ExtensionResponse, status_code=status.HTTP_201_CREATED)
async def create_extension(ext_data: schemas.ExtensionCreate, db: AsyncSession = Depends(get_db)):
    # Проверяем, существует ли уже такой номер
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

    # Пересобираем конфигурационные файлы
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

    # Обновляем конфиги после удаления
    await regenerate_and_save_configs(db)

    return {"status": "success", "message": f"Extension {ext.extension} deleted successfully"}

@app.post("/api/pbx/reload")
async def reload_pbx():
    """Применение конфигурации в Asterisk через AMI"""
    try:
        if not ami_manager.manager:
            await ami_manager.connect()
            if not ami_manager.manager:
                raise HTTPException(status_code=500, detail="Нет подключения к AMI Asterisk")

        await ami_manager.manager.send_action({
            'Action': 'Command',
            'Command': 'core reload'
        })
        
        return {"status": "success", "message": "Конфигурация успешно применена в Asterisk!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка AMI: {str(e)}")