from pydantic import Field
from pydantic_settings import BaseSettings


class GraphConfig(BaseSettings):
    GRAPH_STORE: str = Field(default="neo4j", description="Type of graph store to use for efficient similarity search.")
    GRAPH_NAME: str = Field(default="knowledge_graph", description="Name of the graph database to use.")
