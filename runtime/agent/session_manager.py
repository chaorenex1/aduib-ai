import logging
from typing import Optional

from models import Agent, get_db
from models.agent import AgentSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages agent sessions and lifecycle"""

    @classmethod
    def _create_new_session(cls, agent: Agent, user_id: str) -> int:
        with get_db() as session:
            new_session = AgentSession(agent_id=agent.id, status="active", user_id=user_id)
            session.add(new_session)
            session.commit()
            session.refresh(new_session)
            return new_session.id

    @classmethod
    def create_session(cls, agent: Agent, user_id: str) -> int:
        """create a session ID for the agent"""
        try:
            return cls._create_new_session(agent, user_id)
        except Exception as ex:
            logger.error("Error getting or creating session for agent %s: %s", agent.id, ex)
            raise

    @staticmethod
    def inactivate_session(session_id: str) -> bool:
        with get_db() as session:
            session_id = session_id.strip()
            active_session = session.query(AgentSession).filter_by(id=session_id, status="active").first()
            if active_session:
                active_session.status = "inactive"
                session.commit()
                logger.info("Inactivated session %s for agent %s", session_id, active_session.agent_id)
                return True
            logger.warning("No active session found with ID %s to inactivate", session_id)
            return False

    @staticmethod
    def get_active_session_id(agent: Agent, user_id: str) -> Optional[int]:
        with get_db() as session:
            active_session = (
                session.query(AgentSession)
                .filter_by(
                    agent_id=agent.id,
                    status="active",
                    user_id=user_id,
                )
                .first()
            )
            return active_session.id if active_session else None
