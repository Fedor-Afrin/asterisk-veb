from pydantic import BaseModel, Field
from typing import List, Optional

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class ExtensionPoolCreate(BaseModel):
    start_extension: int = Field(..., ge=100, le=9999)
    end_extension: int = Field(..., ge=100, le=9999)
    transport: Optional[str] = "transport-tls"  # Добавлено поле для приема выбранного транспорта

class ExtensionPoolResponse(BaseModel):
    id: int
    start_extension: int
    end_extension: int
    transport: Optional[str] = "transport-tls"  # Добавлено для отображения в ответе

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    pools: List[ExtensionPoolResponse] = []

    class Config:
        from_attributes = True