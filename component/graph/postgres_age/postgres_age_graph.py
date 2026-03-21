from typing import Any

from component.graph.base_graph import BaseGraphStore
from models import get_db


class PostgresAGEGraphStore(BaseGraphStore):
    @classmethod
    def init_graph(cls, graph_name: str) -> "BaseGraphStore":
        return cls(graph_name)

    def __init__(self, graph_name: str):
        # Initialize connection to PostgreSQL with AGE extension here
        self.graph_name = graph_name
        with get_db() as session:
            session.execute(f"SELECT create_graph('{self.graph_name}');")

    def create_node(self, label: str, properties: dict[str, Any]) -> None:
        with get_db() as session:
            props = ", ".join([f"{key}: '{value}'" for key, value in properties.items()])
            query = f"SELECT * FROM cypher('{self.graph_name}', $$ CREATE (n:{label} {{{props}}}) $$) AS (n agtype);"
            session.execute(query)

    def create_relationship(
        self, start_node_id: str, end_node_id: str, rel_type: str, properties: dict[str, Any]
    ) -> None:
        with get_db() as session:
            props = ", ".join([f"{key}: '{value}'" for key, value in properties.items()])
            query = f"""
            SELECT * FROM cypher('{self.graph_name}', $$
                MATCH (a), (b)
                WHERE a.id = '{start_node_id}' AND b.id = '{end_node_id}'
                CREATE (a)-[r:{rel_type} {{{props}}}]->(b)
            $$) AS (r agtype);
            """
            session.execute(query)

    def query(self, cypher: str) -> list[dict[str, Any]]:
        with get_db() as session:
            query = f"SELECT * FROM cypher('{self.graph_name}', $$ {cypher} $$) AS (result agtype);"
            result = session.execute(query).fetchall()
            return [dict(row) for row in result]

    def delete_node(self, node_id: str) -> None:
        with get_db() as session:
            query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (n) WHERE n.id = '{node_id}' DETACH DELETE n $$) AS (n agtype);"
            session.execute(query)

    def delete_relationship(self, rel_id: str) -> None:
        with get_db() as session:
            query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH ()-[r]->() WHERE r.id = '{rel_id}' DELETE r $$) AS (r agtype);"
            session.execute(query)
