from sqlalchemy import Column, Integer, String, Enum as SQLEnum
import enum
from database import Base

class SIPTransport(str, enum.Enum):
    TLS = "transport-tls"
    UDP = "transport-udp"

class Extension(Base):
    __tablename__ = "extensions"

    id = Column(Integer, primary_key=True, index=True)
    extension = Column(Integer, unique=True, index=True, nullable=False)
    secret = Column(String, nullable=False)
    callerid = Column(String, nullable=True)
    transport = Column(SQLEnum(SIPTransport), default=SIPTransport.TLS, nullable=False)