import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

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


class AuthRole(Base):
    __tablename__ = "auth_role"
    __table_args__ = (
        UniqueConstraint("code", name="uq_auth_role_code"),
        {"comment": "auth role table"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="role id")
    code = Column(String(64), nullable=False, index=True, comment="role code")
    name = Column(String(128), nullable=False, comment="role name")
    description = Column(Text, nullable=True, comment="role description")
    status = Column(String(32), nullable=False, default="active", comment="role status: active or disabled")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="role create time")
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="role update time",
    )


class AuthPermission(Base):
    __tablename__ = "auth_permission"
    __table_args__ = (
        UniqueConstraint("code", name="uq_auth_permission_code"),
        {"comment": "auth permission table"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="permission id")
    code = Column(String(128), nullable=False, index=True, comment="permission code")
    name = Column(String(128), nullable=False, comment="permission name")
    description = Column(Text, nullable=True, comment="permission description")
    group_name = Column(String(128), nullable=True, comment="permission group name")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="permission create time")
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="permission update time",
    )


class AuthUserRole(Base):
    __tablename__ = "auth_user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_auth_user_role_user_role"),
        Index("idx_auth_user_role_user_id", "user_id"),
        Index("idx_auth_user_role_role_id", "role_id"),
        {"comment": "auth user-role relation table"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="user-role relation id")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="user id")
    role_id = Column(Integer, ForeignKey("auth_role.id"), nullable=False, comment="role id")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="relation create time")


class AuthRolePermission(Base):
    __tablename__ = "auth_role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_auth_role_permission_role_permission"),
        Index("idx_auth_role_permission_role_id", "role_id"),
        Index("idx_auth_role_permission_permission_id", "permission_id"),
        {"comment": "auth role-permission relation table"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="role-permission relation id")
    role_id = Column(Integer, ForeignKey("auth_role.id"), nullable=False, comment="role id")
    permission_id = Column(Integer, ForeignKey("auth_permission.id"), nullable=False, comment="permission id")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="relation create time")


class AuthRefreshSession(Base):
    __tablename__ = "auth_refresh_session"
    __table_args__ = (
        Index("ix_auth_refresh_session_user_status", "user_id", "status"),
        {"comment": "refresh-token sessions that support revoke and rotation"},
    )

    id = Column(Integer, primary_key=True, index=True, comment="refresh session id")
    user_id = Column(Integer, nullable=False, index=True, comment="user id")
    token_jti = Column(String, nullable=False, unique=True, index=True, comment="refresh token jti")
    refresh_token_hash = Column(String, nullable=False, comment="sha256 hash of the refresh token")
    status = Column(String, nullable=False, default="active", comment="session status: active/revoked/expired")
    client_type = Column(String, nullable=True, comment="client type, e.g. web/desktop")
    device_label = Column(String, nullable=True, comment="optional device label")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="session create time")
    expires_at = Column(DateTime, nullable=False, comment="refresh token expiry time")
    last_used_at = Column(DateTime, nullable=True, comment="last successful refresh time")
    revoked_at = Column(DateTime, nullable=True, comment="session revoked time")

class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"
    __table_args__ = (
        Index("idx_auth_audit_log_event", "event"),
        Index("idx_auth_audit_log_user_id", "user_id"),
        Index("idx_auth_audit_log_created_at", "created_at"),
        {"comment": "auth audit log table"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="auth audit log id")
    event = Column(String(128), nullable=False, comment="audit event code")
    level = Column(String(32), nullable=False, comment="logging level name")
    trace_id = Column(String(128), nullable=True, comment="request trace id")
    user_id = Column(Integer, nullable=True, comment="related user id")
    username = Column(String(128), nullable=True, comment="related username")
    refresh_jti = Column(String(128), nullable=True, comment="related refresh token jti")
    client_type = Column(String(32), nullable=True, comment="client type")
    device_label = Column(String(128), nullable=True, comment="device label")
    request_ip = Column(String(128), nullable=True, comment="request ip")
    user_agent = Column(Text, nullable=True, comment="user agent")
    reason = Column(Text, nullable=True, comment="failure or audit reason")
    roles = Column(Text, nullable=True, comment="serialized roles")
    permissions = Column(Text, nullable=True, comment="serialized permissions")
    details = Column(Text, nullable=True, comment="serialized extra details")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="audit create time")
