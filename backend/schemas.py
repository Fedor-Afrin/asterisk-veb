from pydantic import BaseModel
from typing import List, Optional
from models import SIPTransport

# --- Номера (Экстеншены) ---
class ExtensionCreate(BaseModel):
    extension: int
    secret: str
    callerid: str
    transport: SIPTransport = SIPTransport.TLS

class ExtensionResponse(ExtensionCreate):
    id: int
    class Config:
        from_attributes = True

# --- Группы вызовов ---
class GroupCreate(BaseModel):
    name: str
    strategy: str
    members: List[int]

class GroupResponse(BaseModel):
    id: int
    name: str
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