from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings


class ClickhouseConfig(BaseSettings):
    CLICKHOUSE_ENABLED: bool = Field(
        description="Enable ClickHouse integration for conversation analytics",
        default=False,
    )

    CLICKHOUSE_HOST: str = Field(
        description="ClickHouse server hostname or IP",
        default="localhost",
    )

    CLICKHOUSE_PORT: PositiveInt = Field(
        description="ClickHouse HTTP interface port",
        default=8123,
    )

    CLICKHOUSE_USER: str = Field(
        description="ClickHouse username",
        default="default",
    )

    CLICKHOUSE_PASSWORD: str = Field(
        description="ClickHouse password",
        default="",
    )

    CLICKHOUSE_DATABASE: str = Field(
        description="ClickHouse database name",
        default="default",
    )
