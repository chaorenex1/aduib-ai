from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class AuthConfig(BaseSettings):
    """
    Configuration settings for authentication
    """

    AUTH_SECRET_KEY: Optional[str] = Field(
        description="Secret key for JWT tokens",
        default=None,
    )

    AUTH_ALGORITHM: str = Field(
        description="Algorithm for JWT tokens",
        default="HS256",
    )

    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: Optional[int] = Field(
        description="Access token expiration in minutes",
        default=43200,
    )

    AUTH_REFRESH_TOKEN_EXPIRE_MINUTES: int = Field(
        description="Refresh token expiration in minutes",
        default=43200,
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
