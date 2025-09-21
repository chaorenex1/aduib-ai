import logging
from contextlib import contextmanager
from typing import Dict, Any, List

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from component.graph.base_graph import BaseGraphStore
from configs import config

logger = logging.getLogger(__name__)


class Neo4jGraphStore(BaseGraphStore):
    def __init__(self):
        self._driver = GraphDatabase.driver(config.neo4j_url, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD))

    @contextmanager
    def _session(self):
        """Context manager for session handling."""
        session = None
        try:
            session = self._driver.session()
            yield session
        except Neo4jError as e:
            logger.error(f"Neo4j error: {e}")
            raise
        finally:
            if session:
                session.close()

    def create_node(self, label: str, properties: Dict[str, Any]) -> None:
        with self._session() as session:
            props = ', '.join([f"{key}: '{value}'" for key, value in properties.items()])
            query = f"CREATE (n:{label} {{{props}}})"
            session.run(query)

    def create_relationship(self, start_node_id: str, end_node_id: str, rel_type: str,
                            properties: Dict[str, Any]) -> None:
        with self._session() as session:
            props = ', '.join([f"{key}: '{value}'" for key, value in properties.items()])
            query = f"""
            MATCH (a), (b)
            WHERE a.id = '{start_node_id}' AND b.id = '{end_node_id}'
            CREATE (a)-[r:{rel_type} {{{props}}}]->(b)
            """
            session.run(query)

    def query(self, cypher: str) -> List[Dict[str, Any]]:
        with self._session() as session:
            result = session.run(cypher)
            return [record.data() for record in result]

    def delete_node(self, node_id: str) -> None:
        with self._session() as session:
            query = f"MATCH (n) WHERE n.id = '{node_id}' DETACH DELETE n"
            session.run(query)

    def delete_relationship(self, rel_id: str) -> None:
        with self._session() as session:
            query = f"MATCH ()-[r]->() WHERE r.id = '{rel_id}' DELETE r"
            session.run(query)


