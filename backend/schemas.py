from pydantic import BaseModel, Field
from models import SIPTransport

class ExtensionCreate(BaseModel):
    extension: int = Field(..., description="Номер экстеншена, например 101")
    secret: str = Field(..., min_length=6, description="Пароль SIP")
    callerid: str = Field(..., description="Имя и номер, например: John Doe <101>")
    transport: SIPTransport = SIPTransport.TLS

class ExtensionResponse(BaseModel):
    id: int
    extension: int
    secret: str  # Администратору нужно видеть пароль
    callerid: str
    transport: SIPTransport

    class Config:
        from_attributes = True