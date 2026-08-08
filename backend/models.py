from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
import datetime
from database import Base

# ================== НОМЕРА (ЭКСТЕНШЕНЫ) ==================
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

# ================== ГРУППЫ ВЫЗОВОВ ==================
group_members = Table(
    'group_members',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('call_groups.id'), primary_key=True),
    Column('extension_id', Integer, ForeignKey('extensions.id'), primary_key=True)
)

class CallGroup(Base):
    __tablename__ = 'call_groups'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    strategy = Column(String, default="ring_all")
    
    members = relationship("Extension", secondary=group_members, backref="groups")

# ================== ТРАНКИ ==================
class Trunk(Base):
    __tablename__ = "trunks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    protocol = Column(String, default="pjsip")  # pjsip, iax2
    host = Column(String, nullable=False)
    username = Column(String, nullable=True)
    secret = Column(String, nullable=True)

# ================== ТРАНКОВЫЕ ГРУППЫ ==================
trunk_group_members = Table(
    'trunk_group_members',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('trunk_groups.id'), primary_key=True),
    Column('trunk_id', Integer, ForeignKey('trunks.id'), primary_key=True)
)

class TrunkGroup(Base):
    __tablename__ = "trunk_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    strategy = Column(String, default="failover")  # failover, load_balance
    prefix = Column(String, default="9", nullable=False)  # Префикс выхода (например, 9)
    
    trunks = relationship("Trunk", secondary=trunk_group_members, backref="groups")

# ================== IVR МЕНЮ ==================
class IVRMenu(Base):
    __tablename__ = "ivr_menus"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    extension = Column(Integer, unique=True)
    greeting_file = Column(String, nullable=True)

# ================== ЗАПИСИ РАЗГОВОРОВ ==================
class CallRecord(Base):
    __tablename__ = "call_records"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    caller = Column(String)
    callee = Column(String)
    duration = Column(Integer)
    filename = Column(String)