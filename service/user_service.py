import json
import logging
from typing import Any, Optional

from configs import config
from libs.context import get_request_audit_metadata
from models.auth_refresh_session import AuthRefreshSession
from models.auth_user import AuthAuditLog, AuthPermission, AuthRole, AuthRolePermission, AuthUserRole, User
from models.engine import get_db, get_session
from sqlalchemy.exc import SQLAlchemyError
from service.error.error import (
    InvalidCredentials,
    InvalidRefreshToken,
    RegistrationDisabled,
    RefreshTokenRevoked,
    UserAlreadyExists,
    UserDisabled,
    UserNotFound,
)
from utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    refresh_token_expiry,
    verify_password,
)
from utils.date import now_local

logger = logging.getLogger(__name__)


class UserService:
    """User authentication service."""

    @staticmethod
    def _serialize_audit_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (list, dict, tuple, set)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @staticmethod
    def _audit_auth_event(level: int, event: str, **fields: Any) -> None:
        request_meta = get_request_audit_metadata()
        fields.setdefault("trace_id", request_meta.get("trace_id"))
        fields.setdefault("request_ip", request_meta.get("request_ip"))
        fields.setdefault("user_agent", request_meta.get("user_agent"))
        payload = " ".join(f"{key}={value!r}" for key, value in fields.items() if value is not None)
        logger.log(level, "auth_audit event=%s %s", event, payload)
        audit_session = None
        try:
            audit_session = get_session()
            details = {
                key: value
                for key, value in fields.items()
                if key
                not in {
                    "trace_id",
                    "user_id",
                    "username",
                    "refresh_jti",
                    "client_type",
                    "device_label",
                    "request_ip",
                    "user_agent",
                    "reason",
                    "roles",
                    "permissions",
                }
            }
            audit_row = AuthAuditLog(
                event=event,
                level=logging.getLevelName(level),
                trace_id=UserService._serialize_audit_value(fields.get("trace_id")),
                user_id=fields.get("user_id"),
                username=fields.get("username"),
                refresh_jti=fields.get("refresh_jti"),
                client_type=fields.get("client_type"),
                device_label=fields.get("device_label"),
                request_ip=UserService._serialize_audit_value(fields.get("request_ip")),
                user_agent=UserService._serialize_audit_value(fields.get("user_agent")),
                reason=UserService._serialize_audit_value(fields.get("reason")),
                roles=UserService._serialize_audit_value(fields.get("roles")),
                permissions=UserService._serialize_audit_value(fields.get("permissions")),
                details=UserService._serialize_audit_value(details) if details else None,
            )
            audit_session.add(audit_row)
            audit_session.commit()
        except Exception as exc:  # pragma: no cover - best effort audit path
            logger.warning("auth_audit_persist_failed event=%s reason=%s", event, exc.__class__.__name__)
            if audit_session is not None:
                audit_session.rollback()
        finally:
            if audit_session is not None:
                audit_session.close()

    @staticmethod
    def _legacy_permissions_for_roles(roles: list[str]) -> list[str]:
        if "admin" in roles:
            return ["admin:*", "setting:read", "user:read"]
        return []

    @classmethod
    def _build_auth_profile(cls, session, user: User) -> dict[str, Any]:
        fallback_roles = [user.role] if user.role else []
        fallback_permissions = cls._legacy_permissions_for_roles(fallback_roles)

        try:
            role_rows = (
                session.query(AuthRole.id, AuthRole.code)
                .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
                .filter(AuthUserRole.user_id == user.id, AuthRole.status == "active")
                .all()
            )
            role_ids = [role_id for role_id, _ in role_rows]
            roles = [code for _, code in role_rows]

            permission_rows = []
            if role_ids:
                permission_rows = (
                    session.query(AuthPermission.code)
                    .join(AuthRolePermission, AuthRolePermission.permission_id == AuthPermission.id)
                    .filter(AuthRolePermission.role_id.in_(role_ids))
                    .all()
                )
            permissions = sorted({code for (code,) in permission_rows})
        except SQLAlchemyError as exc:
            cls._audit_auth_event(
                logging.WARNING,
                "auth_profile_fallback",
                user_id=user.id,
                username=user.username,
                reason=exc.__class__.__name__,
            )
            roles = fallback_roles
            permissions = fallback_permissions

        if not roles:
            roles = fallback_roles
        if not permissions:
            permissions = fallback_permissions

        primary_role = roles[0] if roles else (user.role or "user")
        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "status": user.status,
            "role": primary_role,
            "roles": roles,
            "permissions": permissions,
        }

    @staticmethod
    def _issue_refresh_session(session, user_id: int, *, client_type: str | None = None, device_label: str | None = None) -> str:
        refresh_token = create_refresh_token(user_id)
        token_payload = decode_token(refresh_token)
        token_jti = token_payload.get("jti") if token_payload else None
        if not token_jti:
            raise InvalidRefreshToken("Invalid refresh token")

        refresh_session = AuthRefreshSession(
            user_id=user_id,
            token_jti=str(token_jti),
            refresh_token_hash=hash_token(refresh_token),
            status="active",
            client_type=client_type,
            device_label=device_label,
            expires_at=refresh_token_expiry(),
        )
        session.add(refresh_session)
        session.flush()
        return refresh_token

    @staticmethod
    def _load_refresh_session(
        session,
        refresh_token_str: str,
        *,
        allow_revoked: bool = False,
    ) -> tuple[dict, AuthRefreshSession]:
        payload = decode_token(refresh_token_str)
        if not payload or payload.get("type") != "refresh":
            UserService._audit_auth_event(
                logging.WARNING,
                "refresh_failed_invalid_token",
                reason="decode_failed_or_wrong_type",
            )
            raise InvalidRefreshToken("Invalid refresh token")

        token_jti = payload.get("jti")
        if not token_jti:
            UserService._audit_auth_event(
                logging.WARNING,
                "refresh_failed_invalid_token",
                reason="missing_jti",
            )
            raise InvalidRefreshToken("Invalid refresh token")

        refresh_session = (
            session.query(AuthRefreshSession).filter(AuthRefreshSession.token_jti == str(token_jti)).first()
        )
        if not refresh_session or refresh_session.refresh_token_hash != hash_token(refresh_token_str):
            UserService._audit_auth_event(
                logging.WARNING,
                "refresh_failed_invalid_token",
                refresh_jti=token_jti,
                reason="session_not_found_or_hash_mismatch",
            )
            raise InvalidRefreshToken("Invalid refresh token")
        if refresh_session.status == "revoked" and not allow_revoked:
            UserService._audit_auth_event(
                logging.WARNING,
                "refresh_failed_revoked_token",
                user_id=refresh_session.user_id,
                refresh_jti=token_jti,
                client_type=refresh_session.client_type,
                device_label=refresh_session.device_label,
            )
            raise RefreshTokenRevoked("Refresh token has been revoked")
        if refresh_session.status == "expired":
            UserService._audit_auth_event(
                logging.WARNING,
                "refresh_failed_invalid_token",
                user_id=refresh_session.user_id,
                refresh_jti=token_jti,
                reason="session_marked_expired",
            )
            raise InvalidRefreshToken("Refresh token has expired")

        now = now_local()
        expires_at = refresh_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        if expires_at <= now:
            refresh_session.status = "expired"
            session.commit()
            UserService._audit_auth_event(
                logging.WARNING,
                "refresh_failed_invalid_token",
                user_id=refresh_session.user_id,
                refresh_jti=token_jti,
                reason="token_expired",
            )
            raise InvalidRefreshToken("Refresh token has expired")
        return payload, refresh_session

    @staticmethod
    def register(username: str, password: str, email: Optional[str] = None) -> User:
        """Register a new user."""
        if not config.AUTH_REGISTRATION_ENABLED:
            raise RegistrationDisabled("Registration is currently disabled")
        with get_db() as session:
            existing = session.query(User).filter(User.username == username, User.deleted == 0).first()
            if existing:
                raise UserAlreadyExists(f"Username '{username}' already exists")
            user = User(
                username=username,
                password_hash=hash_password(password),
                email=email,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def login(
        username: str,
        password: str,
        *,
        client_type: str | None = None,
        device_label: str | None = None,
    ) -> dict:
        """Authenticate user and return tokens."""
        with get_db() as session:
            user = session.query(User).filter(User.username == username, User.deleted == 0).first()
            if not user:
                UserService._audit_auth_event(
                    logging.WARNING,
                    "login_failed_invalid_credentials",
                    username=username,
                    client_type=client_type,
                    device_label=device_label,
                )
                raise InvalidCredentials("Invalid username or password")
            if user.status != "active":
                UserService._audit_auth_event(
                    logging.WARNING,
                    "login_failed_disabled_user",
                    user_id=user.id,
                    username=user.username,
                    client_type=client_type,
                    device_label=device_label,
                )
                raise UserDisabled("User account is disabled")
            if not verify_password(password, user.password_hash):
                UserService._audit_auth_event(
                    logging.WARNING,
                    "login_failed_invalid_credentials",
                    user_id=user.id,
                    username=user.username,
                    client_type=client_type,
                    device_label=device_label,
                )
                raise InvalidCredentials("Invalid username or password")
            profile = UserService._build_auth_profile(session, user)
            access_token = create_access_token(user.id, user.username, profile["role"])
            refresh_token = UserService._issue_refresh_session(
                session,
                user.id,
                client_type=client_type,
                device_label=device_label,
            )
            session.commit()
            UserService._audit_auth_event(
                logging.INFO,
                "login_success",
                user_id=user.id,
                username=user.username,
                roles=profile["roles"],
                permissions=profile["permissions"],
                client_type=client_type,
                device_label=device_label,
            )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            **profile,
        }

    @staticmethod
    def refresh_access_token(refresh_token_str: str) -> dict:
        """Refresh the access token using a refresh token."""
        with get_db() as session:
            payload, refresh_session = UserService._load_refresh_session(session, refresh_token_str)
            user_id = int(payload["sub"])
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                UserService._audit_auth_event(
                    logging.WARNING,
                    "refresh_failed_user_not_found",
                    user_id=user_id,
                    refresh_jti=payload.get("jti"),
                )
                raise UserNotFound("User not found")
            if user.status != "active":
                UserService._audit_auth_event(
                    logging.WARNING,
                    "refresh_failed_disabled_user",
                    user_id=user.id,
                    username=user.username,
                    refresh_jti=payload.get("jti"),
                )
                raise UserDisabled("User account is disabled")

            now = now_local()
            refresh_session.status = "revoked"
            refresh_session.last_used_at = now
            refresh_session.revoked_at = now

            profile = UserService._build_auth_profile(session, user)
            access_token = create_access_token(user.id, user.username, profile["role"])
            new_refresh_token = UserService._issue_refresh_session(
                session,
                user.id,
                client_type=refresh_session.client_type,
                device_label=refresh_session.device_label,
            )
            session.commit()
            UserService._audit_auth_event(
                logging.INFO,
                "refresh_success",
                user_id=user.id,
                username=user.username,
                roles=profile["roles"],
                refresh_jti=payload.get("jti"),
                client_type=refresh_session.client_type,
                device_label=refresh_session.device_label,
            )
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    def logout(refresh_token_str: str, current_user_id: int) -> bool:
        """Revoke one refresh-token session for the current user."""
        with get_db() as session:
            payload, refresh_session = UserService._load_refresh_session(
                session,
                refresh_token_str,
                allow_revoked=True,
            )
            user_id = int(payload["sub"])
            if user_id != current_user_id or refresh_session.user_id != current_user_id:
                UserService._audit_auth_event(
                    logging.WARNING,
                    "logout_failed_invalid_token",
                    current_user_id=current_user_id,
                    refresh_jti=payload.get("jti"),
                )
                raise InvalidRefreshToken("Invalid refresh token")
            if refresh_session.status != "revoked":
                refresh_session.status = "revoked"
                refresh_session.revoked_at = now_local()
                session.commit()
            UserService._audit_auth_event(
                logging.INFO,
                "logout_success",
                user_id=current_user_id,
                refresh_jti=payload.get("jti"),
                client_type=refresh_session.client_type,
                device_label=refresh_session.device_label,
            )
        return True

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """Get user by ID."""
        with get_db() as session:
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                raise UserNotFound("User not found")
        return user

    @staticmethod
    def get_user_auth_profile(user_id: int) -> dict[str, Any]:
        with get_db() as session:
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                raise UserNotFound("User not found")
            return UserService._build_auth_profile(session, user)

    @staticmethod
    def update_password(user_id: int, old_password: str, new_password: str) -> bool:
        """Update user password."""
        with get_db() as session:
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                raise UserNotFound("User not found")
            if not verify_password(old_password, user.password_hash):
                raise InvalidCredentials("Old password is incorrect")
            user.password_hash = hash_password(new_password)
            session.commit()
        return True

    @staticmethod
    def disable_user(user_id: int) -> bool:
        """Disable a user account (admin operation)."""
        with get_db() as session:
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                raise UserNotFound("User not found")
            user.status = "disabled"
            session.commit()
        return True

    @staticmethod
    def ensure_admin_exists() -> None:
        """Ensure at least one admin account exists; create default if not."""
        from configs import config

        with get_db() as session:
            admin = session.query(User).filter(User.role == "admin", User.deleted == 0).first()
            if admin:
                logger.info("Admin account already exists: %s", admin.username)
                return
        username = config.AUTH_ADMIN_USERNAME
        password = config.AUTH_ADMIN_PASSWORD
        with get_db() as session:
            existing = session.query(User).filter(User.username == username, User.deleted == 0).first()
            if existing:
                existing.role = "admin"
                session.commit()
                logger.info("Promoted existing user '%s' to admin role", username)
                return
            user = User(
                username=username,
                password_hash=hash_password(password),
                role="admin",
            )
            session.add(user)
            session.commit()
        logger.info("Created default admin account: %s", username)
