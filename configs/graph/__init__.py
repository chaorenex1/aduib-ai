from pydantic import Field
from pydantic_settings import BaseSettings


class GraphConfig(BaseSettings):
    GRAPH_STORE: str = Field(default="", description="Type of graph store to use for efficient similarity search.")
