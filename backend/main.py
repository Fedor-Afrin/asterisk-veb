from fastapi import FastAPI, Request, Depends
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, Base, get_db
import models

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Asterisk Web Management API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Создаем таблицы в БД при старте приложения
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Создаем таблицы (в продакшене лучше использовать Alembic, но для старта идеально)
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
@limiter.limit("5/minute")
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    return {"status": "ok", "message": "Asterisk PBX API is running with Database connected!"}