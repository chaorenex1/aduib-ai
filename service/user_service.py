import logging
from typing import Optional

from configs import config
from models.auth_user import User
from models.engine import get_db
from service.error.error import (
    InvalidCredentials,
    RegistrationDisabled,
    UserAlreadyExists,
    UserDisabled,
    UserNotFound,
)
from utils.auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password

logger = logging.getLogger(__name__)


class UserService:
    """User authentication service."""

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
    def login(username: str, password: str) -> dict:
        """Authenticate user and return tokens."""
        with get_db() as session:
            user = session.query(User).filter(User.username == username, User.deleted == 0).first()
            if not user:
                raise InvalidCredentials("Invalid username or password")
            if user.status != "active":
                raise UserDisabled("User account is disabled")
            if not verify_password(password, user.password_hash):
                raise InvalidCredentials("Invalid username or password")
            access_token = create_access_token(user.id, user.username, user.role)
            refresh_token = create_refresh_token(user.id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
        }

    @staticmethod
    def refresh_access_token(refresh_token_str: str) -> dict:
        """Refresh the access token using a refresh token."""
        payload = decode_token(refresh_token_str)
        if not payload or payload.get("type") != "refresh":
            raise InvalidCredentials("Invalid refresh token")
        user_id = int(payload["sub"])
        with get_db() as session:
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                raise UserNotFound("User not found")
            if user.status != "active":
                raise UserDisabled("User account is disabled")
            access_token = create_access_token(user.id, user.username, user.role)
        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """Get user by ID."""
        with get_db() as session:
            user = session.query(User).filter(User.id == user_id, User.deleted == 0).first()
            if not user:
                raise UserNotFound("User not found")
        return user

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
