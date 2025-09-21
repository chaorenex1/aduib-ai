from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class Neo4jConfig(BaseSettings):
    NEO4J_HOST: str = Field(default="localhost", description="NEO4J_HOST")
    NEO4J_PORT: int = Field(default=7687, description="NEO4J_PORT")
    NEO4J_USERNAME: str = Field(default="", description="NEO4J_USERNAME")
    NEO4J_PASSWORD: str = Field(default="", description="NEO4J_PASSWORD")
    DATABASE: str = Field(default="", description="NEO4J_DATABASE")

    @property
    @computed_field
    def neo4j_url(self) -> str:
        return f"bolt://{self.NEO4J_HOST}:{self.NEO4J_PORT}"
