from controllers.params import AgentCreatePayload, ModelCard, ModelList
from models import get_db
from runtime.agent_mamager import AgentManager
from runtime.entities.llm_entities import ChatCompletionRequest


class AgentService:
    @classmethod
    def create_agent(cls, payload:AgentCreatePayload):
        with get_db() as session:
            from models.agent import Agent
            agent = Agent(
                name=payload.name,
                model_id=payload.model_id,
                description=payload.description,
                tools=payload.tools,
                prompt_template=payload.prompt_template,
                agent_parameters=payload.agent_parameters
            )
            session.add(agent)
            session.commit()
            session.refresh(agent)
            return agent

    @classmethod
    def get_agent_models(cls, agent_id):
        with get_db() as session:
            from models.agent import Agent
            from models.model import Model
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return None
            model = session.query(Model).filter(Model.id == agent.model_id).first()
            return ModelList(data=[
                ModelCard(
                    id=model.name,
                    root=model.provider_name + "/" + model.name,
                    object="model",
                    created=int(model.created_at.timestamp()),
                    owned_by=model.provider_name,
                    max_model_len=model.max_tokens,
                )
            ])

    @classmethod
    async def create_completion(cls, agent_id: int, req:ChatCompletionRequest):
        with get_db() as session:
            from models.agent import Agent
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return None
            runtime = AgentManager()
            from service import CompletionService
            return CompletionService.convert_to_stream(await runtime.handle_agent_request(agent, req), req)
