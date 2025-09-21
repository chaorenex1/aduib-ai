import logging
from typing import Any

from component.storage.base_storage import storage_manager
from models import Agent
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)

class AgentManager:
    def __init__(self):
        self.storage = storage_manager
        self.model_manager = ModelManager()


    def handle_agent_request(self, agent: Agent, query: ChatCompletionRequest)-> Any:
        """Handle agent request"""
        ...