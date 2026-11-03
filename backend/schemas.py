from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any
from models import SIPTransport

# --- Номера (Экстеншены) ---
class ExtensionCreate(BaseModel):
    extension: int
    secret: str
    callerid: str
    transport: SIPTransport = SIPTransport.UDP

    @field_validator("transport", mode="before")
    @classmethod
    def force_udp_transport(cls, value):
        # Keep the API backward-compatible while preventing TLS endpoints.
        return SIPTransport.UDP

class ExtensionResponse(ExtensionCreate):
    id: int
    class Config:
        from_attributes = True

# --- Группы вызовов ---
class GroupCreate(BaseModel):
    name: str
    exten: int          # <--- ДОБАВЛЕН НОМЕР ГРУППЫ
    strategy: str
    members: List[int]

class GroupResponse(BaseModel):
    id: int
    name: str
    exten: int          # <--- ДОБАВЛЕН НОМЕР ГРУППЫ
    strategy: str
    members: List[int]
    class Config:
        from_attributes = True

# --- Транки ---
class TrunkCreate(BaseModel):
    name: str
    protocol: str
    host: str
    username: Optional[str] = None
    secret: Optional[str] = None

class TrunkResponse(TrunkCreate):
    id: int
    class Config:
        from_attributes = True

# --- Транковые группы ---
class TrunkGroupCreate(BaseModel):
    name: str
    strategy: str
    prefix: str = "9"
    trunks: List[int]

class TrunkGroupResponse(BaseModel):
    id: int
    name: str
    strategy: str
    prefix: str
    trunks: List[int]
    class Config:
        from_attributes = True

# --- IVR Меню ---
class IVRCreate(BaseModel):
    name: str
    extension: int
    greeting_file: Optional[str] = None

class IVRResponse(IVRCreate):
    id: int
    class Config:
        from_attributes = True

# --- IVR Меню ---
class IVRCreate(BaseModel):
    name: str
    extension: int
    greeting_file: Optional[str] = None
    options: Dict[str, Any] = {}  # <-- НОВОЕ ПОЛЕ (например: {"1": {"type": "extension", "target": "101"}})

class IVRResponse(IVRCreate):
    id: int
    class Config:
        from_attributes = True
