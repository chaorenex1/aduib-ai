import asyncio
import logging
import time
import re
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Sequence, Union, Generator, List

from component.storage.base_storage import storage_manager
from models import Agent, get_db, ConversationMessage, McpServer, ToolInfo
from models.agent import AgentSession
from runtime.agent.agent_type import AgentRuntimeConfig, AgentTool
from runtime.agent.memory.agent_memory import AgentMemory
from runtime.callbacks.base_callback import Callback
from runtime.entities import (
    TextPromptMessageContent,
    SystemPromptMessage,
    PromptMessageRole,
    UserPromptMessage,
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageFunction,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
)
from runtime.entities.llm_entities import ChatCompletionRequest, ChatCompletionResponseChunkDelta
from runtime.generator.generator import LLMGenerator
from runtime.model_execution import AiModel
from runtime.model_manager import ModelManager, ModelInstance
from runtime.tool.base.tool import Tool
from runtime.tool.entities import ToolProviderType, ToolInvokeResult
from utils import AsyncUtils

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages agent sessions and lifecycle"""

    def __init__(self):
        self._active_sessions: Dict[str, AgentSession] = {}

    async def get_or_create_session(self, agent: Agent) -> str:
        """Get or create a session ID for the agent"""
        try:
            # Use async database operations if available
            session_id = await self._get_active_session_id(agent)
            if session_id:
                return session_id

            return await self._create_new_session(agent)
        except Exception as e:
            logger.error(f"Error getting or creating session for agent {agent.id}: {e}")
            raise

    async def _get_active_session_id(self, agent: Agent) -> Optional[str]:
        """Get active session ID, checking context length limits"""
        loop = asyncio.get_event_loop()

        def _sync_get_session():
            with get_db() as session:
                active_session = session.query(AgentSession).filter_by(
                    agent_id=agent.id, status="active"
                ).first()

                if active_session:
                    from service import ModelService, ConversationMessageService

                    model = ModelService.get_model_by_id(int(agent.model_id))
                    current_context_length = ConversationMessageService.get_context_length(
                        agent.id, active_session.id
                    )

                    if model and current_context_length >= model.max_tokens:
                        # Session exceeded context limit, deactivate it
                        active_session.status = "inactive"
                        session.commit()
                        return None

                    return str(active_session.id)
                return None

        return await loop.run_in_executor(None, _sync_get_session)

    async def _create_new_session(self, agent: Agent) -> str:
        """Create a new session for the agent"""
        loop = asyncio.get_event_loop()

        def _sync_create_session():
            with get_db() as session:
                new_session = AgentSession(agent_id=agent.id, status="active")
                session.add(new_session)
                session.commit()
                session.refresh(new_session)
                return str(new_session.id)

        return await loop.run_in_executor(None, _sync_create_session)


class MemoryManager:
    """Manages agent memory operations"""

    def __init__(self):
        self._agent_memories: Dict[str, AgentMemory] = {}

    def get_or_create_memory(self, agent: Agent, session_id: str) -> AgentMemory:
        """Get or create agent memory instance"""
        memory_key = f"{agent.id}_{session_id}"
        if memory_key not in self._agent_memories:
            self._agent_memories[memory_key] = AgentMemory(
                agent=agent, session_id=session_id
            )
        return self._agent_memories[memory_key]

    async def retrieve_context(self, memory: AgentMemory, user_message: str) -> Dict:
        """Retrieve context from memory"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, memory.retrieve_context, user_message
        )

    def cleanup_memory(self, session_id: str) -> None:
        """Clean up memory for a specific session"""
        keys_to_remove = [
            key for key in self._agent_memories.keys()
            if key.endswith(f"_{session_id}")
        ]

        for key in keys_to_remove:
            self._agent_memories[key].clear_memory()
            del self._agent_memories[key]

        logger.info(f"Cleaned up memory for session: {session_id}")


class ToolManager:
    """Manages agent tools and tool execution"""

    def __init__(self):
        self._tool_cache: Dict[str, List[Tool]] = {}

    def create_agent_runtime_config(self, agent: Agent) -> AgentRuntimeConfig:
        """Create AgentRuntimeConfig with tools"""
        agent_tools: List[Tool] = []

        if agent.tools and len(agent.tools) > 0:
            for tool_data in agent.tools:
                agent_tool = AgentTool.model_validate(tool_data)
                tools = self._load_tools_by_type(agent_tool)
                agent_tools.extend(tools)

        return AgentRuntimeConfig(
            agent=agent,
            tools=agent_tools
        )

    def _load_tools_by_type(self, agent_tool: AgentTool) -> List[Tool]:
        """Load tools based on provider type"""
        if agent_tool.tool_provider_type == ToolProviderType.BUILTIN:
            from runtime.tool.builtin_tool.tool_provider import BuiltinToolController
            return BuiltinToolController().get_tools()

        elif agent_tool.tool_provider_type == ToolProviderType.MCP:
            return self._load_mcp_tools(agent_tool)

        return []

    def _load_mcp_tools(self, agent_tool: AgentTool) -> List[Tool]:
        """Load MCP tools"""
        loop = asyncio.get_event_loop()

        def _sync_load_mcp_tools():
            with get_db() as session:
                tool_info: ToolInfo = session.query(ToolInfo).filter(
                    ToolInfo.id == int(agent_tool.id)
                ).first()

                if tool_info:
                    mcp_server: McpServer = session.query(McpServer).filter(
                        McpServer.server_code == tool_info.mcp_server_code
                    ).first()

                    if mcp_server:
                        from runtime.tool.mcp.tool_provider import McpToolController
                        return McpToolController(
                            server_url=mcp_server.server_url
                        ).get_tools()
            return []

        return loop.run_until_complete(
            asyncio.get_event_loop().run_in_executor(None, _sync_load_mcp_tools)
        )


class ResponseGenerator:
    """Generates responses for agent requests"""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager

    async def generate_response(
        self,
        agent: Agent,
        session_id: str,
        request: ChatCompletionRequest,
        context: Dict
    ) -> Any:
        """Generate response using LLM"""
        try:
            enhanced_messages = self._build_enhanced_messages(request, context, agent)
            request.messages = enhanced_messages

            model_instance = self.model_manager.get_model_instance(model_name=request.model)
            self._apply_agent_parameters(agent, request, model_instance)

            return model_instance.invoke_llm(
                prompt_messages=request,
                callbacks=[
                    AgentMessageRecordCallback(
                        agent=agent,
                        session_id=session_id,
                        agent_manager=self
                    )
                ],
            )
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_tool_response(
        self,
        agent_runtime_config: AgentRuntimeConfig,
        user_message: str
    ) -> str:
        """Generate response using tools"""
        try:
            tool_args = LLMGenerator.choice_tool_invoke(
                agent_runtime_config.tools, user_message
            )
            tool_name = tool_args.get("tool_name")

            if not tool_name:
                return self._extract_tool_response(user_message)

            tool_arguments = tool_args.get("tool_arguments", {})
            tool_map = {tool.entity.name: tool for tool in agent_runtime_config.tools}
            tool = tool_map.get(tool_name)

            if tool:
                tool_invoke_result = tool.invoke(tool_arguments)
                result: ToolInvokeResult = next(tool_invoke_result)

                if result.success:
                    # Remove used tool and recursively call again
                    remaining_tools = [
                        tool for tool in agent_runtime_config.tools
                        if tool.entity.name != tool_name
                    ]

                    updated_config = AgentRuntimeConfig(
                        agent=agent_runtime_config.agent,
                        tools=remaining_tools
                    )

                    tool_response = f"\n<tool_response>\n{str(result.data)}\n</tool_response>"
                    return await self.generate_tool_response(
                        updated_config, user_message + tool_response
                    )

            return ""
        except Exception as e:
            logger.error(f"Error generating tool response: {e}")
            raise

    def _extract_tool_response(self, user_message: str) -> str:
        """Extract tool response from message"""
        match = re.search(r"<tool_response>(.*?)</tool_response>", user_message, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _build_enhanced_messages(
        self,
        query: ChatCompletionRequest,
        context: Dict,
        agent: Agent
    ) -> List:
        """Build enhanced messages with context"""
        system_message = self._get_system_message(query, agent)
        last_message = query.messages[-1]

        messages = [system_message, last_message] if system_message else [last_message]

        if agent.enabled_memory == 1:
            messages = self._add_memory_context(messages, context, agent)
        else:
            logger.debug("Memory is disabled for this agent.")
            messages = query.messages

        return messages

    def _get_system_message(self, query: ChatCompletionRequest, agent: Agent):
        """Get system message from query or agent template"""
        first_message = query.messages[0]

        if (first_message.role == PromptMessageRole.SYSTEM and
            first_message.content):
            return first_message

        if agent.prompt_template:
            return SystemPromptMessage(
                role=PromptMessageRole.SYSTEM,
                content=agent.prompt_template
            )

        return None

    def _add_memory_context(self, messages: List, context: Dict, agent: Agent) -> List:
        """Add memory context to messages"""
        # Add short-term memory
        if context.get("short_term") and len(context["short_term"]) > 0:
            for memory in context["short_term"]:
                if memory.get("user_message"):
                    messages.insert(-1, UserPromptMessage(
                        role=PromptMessageRole.USER,
                        content=memory["user_message"]
                    ))
                if memory.get("assistant_message"):
                    messages.insert(-1, AssistantPromptMessage(
                        role=PromptMessageRole.ASSISTANT,
                        content=memory["assistant_message"]
                    ))

        # Add long-term memory
        if context.get("long_term") and len(context["long_term"]) > 0:
            relevant_memories = context["long_term"]
            if relevant_memories:
                context_content = self._format_long_term_memory(relevant_memories)
                messages = self._add_context_to_system_message(messages, context_content, agent)

        return messages

    def _format_long_term_memory(self, memories: List[Dict]) -> str:
        """Format long-term memory for context"""
        memory_entries = []
        for mem in memories:
            user_msg = mem.get('user_message', '')
            assistant_msg = mem.get('assistant_message', '')
            memory_entries.append(
                f"<conversation>\n<user>{user_msg}</user>\n"
                f"<assistant>{assistant_msg}</assistant>\n</conversation>"
            )

        return (
            "<historical_conversations>\n" +
            "\n".join(memory_entries) +
            "\n</historical_conversations>"
        )

    def _add_context_to_system_message(
        self,
        messages: List,
        context_content: str,
        agent: Agent
    ) -> List:
        """Add context to system message"""
        if messages and messages[0].role == PromptMessageRole.SYSTEM:
            messages[0].content = messages[0].content + "\n\n" + context_content
        else:
            system_content = agent.prompt_template + "\n\n" + context_content
            messages.insert(0, SystemPromptMessage(
                role=PromptMessageRole.SYSTEM,
                content=system_content
            ))
        return messages

    def _apply_agent_parameters(
        self,
        agent: Agent,
        request: ChatCompletionRequest,
        model_instance: ModelInstance
    ) -> None:
        """Apply agent parameters to request and model"""
        if not agent.agent_parameters:
            return

        parameters = agent.agent_parameters

        # Apply request parameters
        parameter_mapping = {
            "temperature": "temperature",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "presence_penalty": "presence_penalty",
            "max_tokens": "max_completion_tokens"
        }

        for param_key, request_key in parameter_mapping.items():
            if param_key in parameters:
                setattr(request, request_key, parameters[param_key])

        # Apply model instance parameters
        if "api_base" in parameters:
            model_instance.provider.provider_credential.credentials["api_base"] = \
                parameters["api_base"]

        if "api_key" in parameters:
            model_instance.provider.provider_credential.credentials["api_key"] = \
                parameters["api_key"]


class MessageProcessor:
    """Processes user messages for agent requests"""

    @staticmethod
    def get_user_message(content: Any) -> str:
        """Extract user message from content"""
        if isinstance(content, str):
            return content
        elif isinstance(content, TextPromptMessageContent):
            return content.text
        elif isinstance(content, list):
            return "".join([
                c.text if isinstance(c, TextPromptMessageContent) else str(c)
                for c in content
            ])
        else:
            raise ValueError("Unsupported message content type")


class AgentManager:
    """Main agent manager coordinating all components"""

    def __init__(self):
        self.storage = storage_manager
        self.model_manager = ModelManager()
        self.session_manager = SessionManager()
        self.memory_manager = MemoryManager()
        self.tool_manager = ToolManager()
        self.response_generator = ResponseGenerator(self.model_manager)
        self.message_processor = MessageProcessor()
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def handle_agent_request(self, agent: Agent, request: ChatCompletionRequest) -> Any:
        """Handle agent request with proper error handling"""
        try:
            # Get or create session
            session_id = await self.session_manager.get_or_create_session(agent)
            logger.debug("Using session_id: %s for agent_id: %d", session_id, agent.id)

            # Get or create memory
            memory = self.memory_manager.get_or_create_memory(agent, session_id)

            # Process user message
            user_message = self.message_processor.get_user_message(
                request.messages[-1].content
            )

            # Create runtime config
            agent_runtime_config = self.tool_manager.create_agent_runtime_config(agent)

            if agent_runtime_config.tools and len(agent_runtime_config.tools) > 0:
                return await self._handle_tool_request(
                    agent_runtime_config, user_message, request
                )
            else:
                return await self._handle_standard_request(
                    agent, session_id, request, user_message, memory
                )

        except Exception as e:
            logger.error(f"Error handling agent request: {e}")
            raise

    async def _handle_tool_request(
        self,
        agent_runtime_config: AgentRuntimeConfig,
        user_message: str,
        request: ChatCompletionRequest
    ) -> Generator[ChatCompletionResponseChunk, None, None]:
        """Handle request with tools"""
        response = await self.response_generator.generate_tool_response(
            agent_runtime_config, user_message
        )

        def tool_generator() -> Generator[ChatCompletionResponseChunk, None, None]:
            yield ChatCompletionResponseChunk(
                id="chatcmpl-xxxx",
                object="chat.completion.chunk",
                created=int(time.time()),
                model=request.model,
                prompt_messages=request.messages,
                choices=[
                    ChatCompletionResponseChunkDelta(
                        index=0,
                        delta=AssistantPromptMessage(
                            role=PromptMessageRole.ASSISTANT,
                            content=response
                        ),
                        finish_reason="stop"
                    )
                ],
            )

        return tool_generator()

    async def _handle_standard_request(
        self,
        agent: Agent,
        session_id: str,
        request: ChatCompletionRequest,
        user_message: str,
        memory: AgentMemory
    ) -> Any:
        """Handle standard request without tools"""
        context = await self.memory_manager.retrieve_context(memory, user_message)
        logger.debug(f"Retrieved context: {context}")

        return await self.response_generator.generate_response(
            agent, session_id, request, context
        )

    def cleanup_memory(self, session_id: str) -> None:
        """Clean up memory for a session"""
        self.memory_manager.cleanup_memory(session_id)


class AgentMessageRecordCallback(Callback):
    """Callback for recording agent messages"""

    def __init__(self, agent: Agent, session_id: str, agent_manager: ResponseGenerator):
        self.user_message = ""
        self.agent = agent
        self.session_id = session_id
        self.agent_manager = agent_manager

    def on_before_invoke(
        self,
        llm_instance: AiModel,
        model: str,
        credentials: dict,
        prompt_messages: Union[list[PromptMessage], str],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        include_reasoning: bool = False,
        user: Optional[str] = None,
    ) -> None:
        role: str = ""
        system_prompt: str = ""
        content: str = ""

        if isinstance(prompt_messages, list) and prompt_messages:
            role = prompt_messages[-1].role.value
            if prompt_messages[-1].content:
                for c in prompt_messages[-1].content:
                    if isinstance(c, str):
                        content += c
                    else:
                        content += c.data or c.text
            system_prompt = prompt_messages[0].content if prompt_messages[0].role.value == "system" else ""
        elif isinstance(prompt_messages, str):
            role = "user"
            content = prompt_messages

        conversation_message = ConversationMessage(
            message_id=model_parameters.get("message_id"),
            model_name=model,
            provider_name=llm_instance.provider_name,
            role=role,
            content=content,
            system_prompt=system_prompt,
            agent_id=self.agent.id,
            agent_session_id=int(self.session_id),
        )

        self.user_message = content
        from event.event_manager import event_manager_context

        event_manager = event_manager_context.get()
        AsyncUtils.run_async_gen(
            event_manager.emit(event="agent_from_conversation_message", message=conversation_message, callback=self)
        )

    def on_new_chunk(
        self,
        llm_instance: AiModel,
        chunk: ChatCompletionResponseChunk,
        model: str,
        credentials: dict,
        prompt_messages: Sequence[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        include_reasoning: bool = False,
        user: Optional[str] = None,
    ):
        pass

    def on_after_invoke(
        self,
        llm_instance: AiModel,
        result: ChatCompletionResponse,
        model: str,
        credentials: dict,
        prompt_messages: Sequence[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        include_reasoning: bool = False,
        user: Optional[str] = None,
    ) -> None:
        message_id = model_parameters.get("message_id")
        if not message_id:
            return

        message_content: str = ""
        if isinstance(result.message.content, str):
            message_content = result.message.content
        elif isinstance(result.message.content, list):
            message_content = "".join([content.data for content in result.message.content])

        # Remove <think> and </think> including the content between them
        message_content = re.sub(r"<think>.*?</think>", "", message_content, flags=re.DOTALL)

        message = ConversationMessage(
            message_id=message_id,
            model_name=model,
            provider_name=llm_instance.provider_name,
            role=result.message.role.value,
            content=message_content,
            system_prompt="",
            usage=result.usage.model_dump_json(exclude_none=True),
            state="success",
            agent_id=self.agent.id,
            agent_session_id=int(self.session_id),
        )

        from event.event_manager import event_manager_context
        event_manager = event_manager_context.get()
        AsyncUtils.run_async_gen(
            event_manager.emit(event="agent_from_conversation_message", message=message, callback=self)
        )

    def on_invoke_error(
        self,
        llm_instance: AiModel,
        ex: Exception,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        include_reasoning: bool = False,
        user: Optional[str] = None,
    ) -> None:
        pass