from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class DBConfig(BaseSettings):
    DB_DRIVER: str = Field(default="postgresql", description="Database driver")
    DB_HOST: str = Field(default="10.0.0.96", description="Database host")
    DB_PORT: int = Field(default=5432, description="Database port")
    DB_USERNAME: str = Field(default="postgres", description="Database username")
    DB_PASSWORD: str = Field(default="postgres", description="Database password")
    DB_DATABASE: str = Field(default="aduib_ai", description="Database name")
    DB_CHARSET: str = Field(default="utf8", description="Database charset")
    DB_EXTRAS: str = Field(default="", description="Database extras")
    POOL_SIZE: int = Field(default=50, description="Database connection pool size")

    @computed_field
    @property
    def DATABASE_URI(self) -> str:
        db_extras = (
            f"{self.DB_EXTRAS}&client_encoding={self.DB_CHARSET}" if self.DB_CHARSET else self.DB_EXTRAS
        ).strip("&")
        db_extras = f"?{db_extras}" if db_extras else ""
        return (
            f"{self.DB_DRIVER}://"
            f"{quote_plus(self.DB_USERNAME)}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"
            f"{db_extras}"
        )
