from fastapi import FastAPI, Request, Depends, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import bcrypt

from database import engine, Base, get_db
import models
import schemas

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Asterisk Web Management API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
@limiter.limit("5/minute")
async def root(request: Request):
    return {"status": "ok", "message": "Asterisk PBX API is running with Database connected!"}

@app.post("/api/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == user_data.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Хэшируем пароль через чистый bcrypt (обрезаем до 72 байт на всякий случай)
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
        end_extension=pool_data.end_extension
    )

    db.add(new_pool)
    await db.commit()
    return {"status": "success", "message": f"Pool {pool_data.start_extension}-{pool_data.end_extension} created for user {user.username}"}