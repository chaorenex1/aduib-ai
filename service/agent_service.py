from typing import Any

from controllers.params import AgentCreatePayload
from models import get_db
from runtime.entities import LLMRequest


class AgentService:
    @classmethod
    def create_agent(cls, payload: AgentCreatePayload):
        with get_db() as session:
            from models.agent import Agent

            agent = Agent(
                name=payload.name,
                model_id=payload.model_id,
                description=payload.description,
                tools=payload.tools,
                prompt_template=payload.prompt_template,
                agent_parameters=payload.agent_parameters,
            )
            session.add(agent)
            session.commit()
            session.refresh(agent)
            return agent

    @classmethod
    async def arun(cls, req: LLMRequest) -> Any:
        from libs.context import app_context

        return await app_context.get().agent_manager.arun_response(request=req)
