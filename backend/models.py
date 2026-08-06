from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Связь с пулами номеров пользователя
    pools = relationship("ExtensionPool", back_populates="owner", cascade="all, delete-orphan")


class ExtensionPool(Base):
    __tablename__ = "extension_pools"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_extension = Column(Integer, nullable=False)  # Начало пула, например 100
    end_extension = Column(Integer, nullable=False)    # Конец пула, например 110

    owner = relationship("User", back_populates="pools")