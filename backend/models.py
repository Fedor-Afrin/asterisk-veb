from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    pools = relationship("ExtensionPool", back_populates="user", cascade="all, delete-orphan")

class ExtensionPool(Base):
    __tablename__ = "extension_pools"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_extension = Column(Integer, nullable=False)
    end_extension = Column(Integer, nullable=False)
    transport = Column(String, default="transport-tls", nullable=False)

    user = relationship("User", back_populates="pools")