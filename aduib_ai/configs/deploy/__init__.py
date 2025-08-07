from itertools import product
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class DeploymentConfig(BaseSettings):
    APP_NAME: str = Field(default="aduib_ai", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    APP_HOST: str = Field(default="",description="Application host")
    APP_PORT: int = Field(default=5001,description="Application port")
    DEPLOY_ENV: str = Field(
        description="Deployment environment (e.g., 'PRODUCTION', 'DEVELOPMENT'), default to PRODUCTION",
        default="PRODUCTION",
    )
    DEBUG: bool = Field(default=True, description="Enable debug mode")
