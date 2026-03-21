import datetime

from sqlalchemy import Column, DateTime, Integer, String

from models.base import Base


class User(Base):
    __tablename__ = "user"
    __table_args__ = {
        "comment": "user table",
    }
    id = Column(Integer, primary_key=True, index=True, comment="user id")
    username = Column(String, unique=True, index=True, nullable=False, comment="username")
    password_hash = Column(String, nullable=False, comment="bcrypt password hash")
    email = Column(String, nullable=True, comment="user email")
    role = Column(String, default="user", comment="user role: admin or user")
    status = Column(String, default="active", comment="user status: active or disabled")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="user create time")
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="user update time",
    )
    deleted = Column(Integer, default=0, comment="user delete flag")
