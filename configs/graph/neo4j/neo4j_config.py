from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class Neo4jConfig(BaseSettings):
    HOST: str = Field(default="localhost", description="NEO4J_HOST")
    PORT: int = Field(default=7687, description="NEO4J_PORT")
    USERNAME: str = Field(default="", description="NEO4J_USERNAME")
    PASSWORD: str = Field(default="", description="NEO4J_PASSWORD")
    DATABASE: str = Field(default="", description="NEO4J_DATABASE")

    @property
    @computed_field
    def get_url(self) -> str:
        return f"bolt://{self.HOST}:{self.PORT}"
