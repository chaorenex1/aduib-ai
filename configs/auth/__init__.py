from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class AuthConfig(BaseSettings):
    """
    Configuration settings for authentication
    """

    AUTH_ENABLED: bool = Field(
        description="Whether authentication is enabled",
        default=False,
    )

    AUTH_SECRET_KEY: Optional[str] = Field(
        description="Secret key for JWT tokens",
        default=None,
    )

    AUTH_ALGORITHM: str = Field(
        description="Algorithm for JWT tokens",
        default="HS256",
    )

    AUTH_EXPIRE_MINUTES: int = Field(
        description="JWT token expiration in minutes",
        default=60 * 24 * 7,  # 7 days
    )

    AUTH_REGISTRATION_ENABLED: bool = Field(
        description="Whether user self-registration is enabled",
        default=True,
    )

    AUTH_ADMIN_USERNAME: str = Field(
        description="Default admin username created on first startup",
        default="admin",
    )

    AUTH_ADMIN_PASSWORD: str = Field(
        description="Default admin password created on first startup",
        default="Adm!n@2026#Sec",
    )
