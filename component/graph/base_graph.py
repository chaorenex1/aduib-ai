from abc import ABC, abstractmethod
from typing import Any

from configs import config


class BaseGraphStore(ABC):
    """抽象图操作接口"""

    @classmethod
    def init_graph(cls, graph_name: str) -> "BaseGraphStore":
        pass

    @abstractmethod
    def create_node(self, label: str, properties: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def create_relationship(
        self, start_node_id: str, end_node_id: str, rel_type: str, properties: dict[str, Any]
    ) -> None:
        pass

    @abstractmethod
    def query(self, cypher: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def delete_node(self, node_id: str) -> None:
        pass

    @abstractmethod
    def delete_relationship(self, rel_id: str) -> None:
        pass


class GraphManager(BaseGraphStore):
    def __init__(self, graph_name: str):
        self.graph_name = graph_name
        self.graph_instance = self.init_graph(self.graph_name)

    def create_node(self, label: str, properties: dict[str, Any]) -> None:
        self.graph_instance.create_node(label=label, properties=properties)

    def create_relationship(
        self, start_node_id: str, end_node_id: str, rel_type: str, properties: dict[str, Any]
    ) -> None:
        self.graph_instance.create_relationship(
            start_node_id=start_node_id, end_node_id=end_node_id, rel_type=rel_type, properties=properties
        )

    def query(self, cypher: str) -> list[dict[str, Any]]:
        return self.graph_instance.query(cypher=cypher)

    def delete_node(self, node_id: str) -> None:
        self.graph_instance.delete_node(node_id=node_id)

    def delete_relationship(self, rel_id: str) -> None:
        self.graph_instance.delete_relationship(rel_id=rel_id)

    def init_graph(self, graph_name: str) -> BaseGraphStore:
        graph_cls = self.get_graph_instance(config.GRAPH_STORE)
        return graph_cls.init_graph(graph_name)

    @staticmethod
    def get_graph_instance(graph_type: str) -> type[BaseGraphStore]:
        match graph_type:
            case "neo4j":
                from .neo4j.neo4j_graph import Neo4jGraphStore

                return Neo4jGraphStore
            case "postgres_age":
                from .postgres_age.postgres_age_graph import PostgresAGEGraphStore

                return PostgresAGEGraphStore
            case _:
                raise ValueError(f"Unsupported graph type: {graph_type}")
