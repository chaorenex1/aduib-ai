from pydantic import Field
from pydantic_settings import BaseSettings


class IdConfig(BaseSettings):
    SNOWFLAKE_WORKER_ID: int = Field(
        default=1,
        description="Snowflake worker ID",
    )
    SNOWFLAKE_DATACENTER_ID: int = Field(
        default=1,
        description="Snowflake datacenter ID",
    )