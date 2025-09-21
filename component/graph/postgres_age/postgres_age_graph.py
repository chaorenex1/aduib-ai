from typing import Dict, Any, List

from component.graph.base_graph import BaseGraphStore
from configs import config
from models import get_db


class PostgresAGEGraphStore(BaseGraphStore):
    def __init__(self):
        self.graph_name = config.GRAPH_NAME
        # Initialize connection to PostgreSQL with AGE extension here
        with get_db() as session:
            session.execute(f"SELECT create_graph('{self.graph_name}');")

    def create_node(self, label: str, properties: Dict[str, Any]) -> None:
        with get_db() as session:
            props = ', '.join([f"{key}: '{value}'" for key, value in properties.items()])
            query = f"SELECT * FROM cypher('{self.graph_name}', $$ CREATE (n:{label} {{{props}}}) $$) AS (n agtype);"
            session.execute(query)

    def create_relationship(self, start_node_id: str, end_node_id: str, rel_type: str,
                            properties: Dict[str, Any]) -> None:
        with get_db() as session:
            props = ', '.join([f"{key}: '{value}'" for key, value in properties.items()])
            query = f"""
            SELECT * FROM cypher('{self.graph_name}', $$
                MATCH (a), (b)
                WHERE a.id = '{start_node_id}' AND b.id = '{end_node_id}'
                CREATE (a)-[r:{rel_type} {{{props}}}]->(b)
            $$) AS (r agtype);
            """
            session.execute(query)

    def query(self, cypher: str) -> List[Dict[str, Any]]:
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

