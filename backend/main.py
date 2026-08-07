from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import bcrypt
import os
import subprocess

from database import engine, Base, get_db
import models
import schemas
import pbx_config
from ami_client import ami_manager

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Asterisk Web Management API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Безопасное подключение к Asterisk AMI при старте бэкенда
    try:
        await ami_manager.connect()
    except Exception:
        pass

# Раздача главной страницы фронтенда
@app.get("/")
@limiter.limit("10/minute")
async def read_index(request: Request):
    return FileResponse("/frontend/index.html")

# Подключение статических файлов (CSS, JS)
app.mount("/static", StaticFiles(directory="/frontend"), name="static")

@app.post("/api/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == user_data.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    password_bytes = user_data.password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    new_user = models.User(username=user_data.username, hashed_password=hashed_password)
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@app.post("/api/users/{user_id}/pools", status_code=status.HTTP_201_CREATED)
async def create_extension_pool(user_id: int, pool_data: schemas.ExtensionPoolCreate, db: AsyncSession = Depends(get_db)):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if pool_data.start_extension > pool_data.end_extension:
        raise HTTPException(status_code=400, detail="Start extension cannot be greater than end extension")

    new_pool = models.ExtensionPool(
        user_id=user_id,
        start_extension=pool_data.start_extension,
        end_extension=pool_data.end_extension,
        transport=getattr(pool_data, 'transport', 'transport-tls')
    )
    
    db.add(new_pool)
    await db.commit()

    # --- Генерация конфигов с отладкой ---
    try:
        result = await db.execute(select(models.ExtensionPool).options(selectinload(models.ExtensionPool.user)))
        all_pools = result.scalars().all()

        pools_data = [
            {
                "start_extension": p.start_extension,
                "end_extension": p.end_extension,
                "username": p.user.username,
                "transport": getattr(p, 'transport', 'transport-tls')
            }
            for p in all_pools
        ]
        
        print(f"DEBUG: Found pools in DB for generation: {pools_data}")

        if pools_data:
            success, path_err = pbx_config.save_pjsip_config(pools_data)
            print(f"DEBUG: save_pjsip_config result: {success}, path/err: {path_err}")

            success_ext, path_err_ext = pbx_config.save_extensions_config(pools_data)
            print(f"DEBUG: save_extensions_config result: {success_ext}, path/err: {path_err_ext}")
        else:
            print("DEBUG: WARNING! pools_data is empty, skipping config generation.")

    except Exception as e:
        print(f"CONFIG GENERATION ERROR: {e}")

    return {
        "status": "success", 
        "message": f"Pool {pool_data.start_extension}-{pool_data.end_extension} created successfully!"
    }

@app.get("/api/users", response_model=list[schemas.UserResponse])
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).options(selectinload(models.User.pools)))
    users = result.scalars().all()
    return users

@app.get("/api/pbx/status")
async def get_pbx_status():
    """Эндпоинт для получения статусов абонентов из Asterisk в реальном времени"""
    status_data = await ami_manager.get_peers_status()
    return status_data

@app.post("/api/pbx/reload")
async def reload_pbx():
    """Эндпоинт для применения конфигурации в Asterisk через AMI"""
    try:
        # Проверяем, есть ли живое подключение, если нет — пробуем подключиться
        if not ami_manager.manager:
            await ami_manager.connect()
            if not ami_manager.manager:
                raise HTTPException(status_code=500, detail="Нет подключения к AMI Asterisk")

        # Отправляем консольную команду core reload через менеджер
        response = await ami_manager.manager.send_action({
            'Action': 'Command',
            'Command': 'core reload'
        })
        
        return {"status": "success", "message": "Конфигурация успешно применена через AMI!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка AMI: {str(e)}")