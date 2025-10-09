import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Sequence, Union, Generator

from component.storage.base_storage import storage_manager
from models import Agent, get_db, ConversationMessage, McpServer
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


class AgentManager:
    def __init__(self):
        self.storage = storage_manager
        self.model_manager = ModelManager()
        self.agent_memories: Dict[str, AgentMemory] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)

    def get_or_create_memory(self, agent: Agent, session_id: str) -> AgentMemory:
        """获取或创建 agent 内存实例"""
        memory_key = f"{agent.id}_{session_id}"
        if memory_key not in self.agent_memories:
            self.agent_memories[memory_key] = AgentMemory(agent=agent, session_id=session_id)
        return self.agent_memories[memory_key]

    def _get_or_create_session_id(self, agent: Agent) -> str:
        """获取或创建会话ID"""
        with get_db() as session:
            active_session = session.query(AgentSession).filter_by(agent_id=agent.id, status="active").first()
            if active_session:
                from service import ModelService, ConversationMessageService

                model = ModelService.get_model_by_id(int(agent.model_id))
                currecnt_context_length = ConversationMessageService.get_context_length(agent.id, active_session.id)
                if model and currecnt_context_length >= model.max_tokens:
                    active_session.status = "inactive"
                    session.commit()
                    new_session = AgentSession(agent_id=agent.id, status="active")
                    session.add(new_session)
                    session.commit()
                    session.refresh(new_session)
                    return str(new_session.id)
                else:
                    return active_session.id
            else:
                new_session = AgentSession(agent_id=agent.id, status="active")
                session.add(new_session)
                session.commit()
                session.refresh(new_session)
                return str(new_session.id)

    def _get_user_message(self, content: Any) -> str:
        """构建用户消息"""
        if isinstance(content, str):
            return content
        elif isinstance(content, TextPromptMessageContent):
            return content.text
        elif isinstance(content, list):
            return "".join([c.text if isinstance(c, TextPromptMessageContent) else str(c) for c in content])
        else:
            raise ValueError("Unsupported message content type")

    async def handle_agent_request(self, agent: Agent, req: ChatCompletionRequest) -> Any:
        """Handle agent request"""
        try:
            # 获取会话ID，如果没有则使用默认值
            session_id = self._get_or_create_session_id(agent)
            logger.debug("Using session_id: %s for agent_id: %d", session_id, agent.id)

            # 获取或创建内存实例
            memory = self.get_or_create_memory(agent, session_id)

            # 构建用户消息
            user_message = self._get_user_message(req.messages[-1].content)

            agent_runtime_config:AgentRuntimeConfig = self._create_agent_runtime_config(agent)

            if agent_runtime_config.tools and len(agent_runtime_config.tools) > 0:
                # 调用模型生成响应
                response = await self._generate_tool_response(agent_runtime_config, user_message)
                def tool_generator()-> Generator[ChatCompletionResponseChunk, None, None]:
                    yield ChatCompletionResponseChunk(
                        id="chatcmpl-xxxx",
                        object="chat.completion.chunk",
                        created=int(time.time()),
                        model=req.model,
                        prompt_messages=req.messages,
                        choices=[
                            ChatCompletionResponseChunkDelta(
                                index=0, delta=AssistantPromptMessage(role=PromptMessageRole.ASSISTANT, content=response), finish_reason="stop"
                            )
                        ],
                    )
                return tool_generator()
            else:
                # 从内存中检索上下文
                context = await asyncio.get_event_loop().run_in_executor(
                    self.executor, memory.retrieve_context, user_message
                )
                logger.debug(f"Retrieved context: {context}")

                # 调用模型生成响应
                response = await self._generate_response(agent, session_id, req, context)
                return response

        except Exception as e:
            logger.error(f"Error handling agent request: {e}")
            raise

    async def _generate_response(self, agent: Agent, session_id: str, req: ChatCompletionRequest, context: Dict) -> Any:
        """生成响应"""
        try:
            # 构建增强的提示词，包含上下文信息
            enhanced_messages = self._build_enhanced_messages(req, context, agent)
            req.messages = enhanced_messages


            from runtime.model_manager import ModelManager
            model_manager = ModelManager()
            model_instance = model_manager.get_model_instance(model_name=req.model)

            # 构建微调参数
            self._build_agent_parameters(agent, req,model_instance)
            return model_instance.invoke_llm(
                prompt_messages=req,
                callbacks=[AgentMessageRecordCallback(agent=agent, session_id=session_id, agent_manager=self)],
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    def _build_enhanced_messages(self, query: ChatCompletionRequest, context: Dict, agent: Agent) -> list:
        """构建包含上下文的消息列表"""
        system_messages = query.messages[0]
        if system_messages.role == PromptMessageRole.SYSTEM and system_messages.content:
            system_messages.content = system_messages.content
        else:
            if agent.prompt_template:
                system_messages = SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=agent.prompt_template)
            else:
                system_messages=None
        last_message = query.messages[-1]
        if system_messages:
            messages = [system_messages, last_message]
        else:
            messages = [last_message]

        if agent.enabled_memory==1:
            # 添加短期记忆上下文
            if context.get("short_term") and len(context["short_term"]) > 0:
                for memory in context["short_term"]:
                    if memory.get("user_message"):
                        messages.insert(-1, UserPromptMessage(role=PromptMessageRole.USER, content=memory["user_message"]))
                    if memory.get("assistant_message"):
                        messages.insert(
                            -1,
                            AssistantPromptMessage(role=PromptMessageRole.ASSISTANT, content=memory["assistant_message"]),
                        )

            # 添加长期记忆相关上下文
            if context.get("long_term") and len(context["long_term"]) > 0:
                relevant_memories = context["long_term"]
                if relevant_memories:
                    context_content = (
                        "<historical_conversations>\n"
                        + "\n".join(
                            [
                                f"<conversation>\n<user>{mem.get('user_message', '')}</user>\n<assistant>{mem.get('assistant_message', '')}</assistant>\n</conversation>"
                                for mem in relevant_memories
                            ]
                        )
                        + "\n</historical_conversations>"
                    )
                    if messages and messages[0].role == PromptMessageRole.SYSTEM:
                        messages[0].content = messages[0].content + "\n\n" + context_content
                    else:
                        messages.insert(
                            0,
                            SystemPromptMessage(
                                role=PromptMessageRole.SYSTEM, content=agent.prompt_template + "\n\n" + context_content
                            ),
                        )
        else:
            logger.debug("Memory is disabled for this agent.")
            messages=query.messages

        return messages

    def cleanup_memory(self, session_id: str) -> None:
        """清理指定会话的内存"""
        keys_to_remove = [key for key in self.agent_memories.keys() if key.endswith(f"_{session_id}")]
        for key in keys_to_remove:
            self.agent_memories[key].clear_memory()
            del self.agent_memories[key]
        logger.info(f"Cleaned up memory for session: {session_id}")

    def _build_agent_parameters(self, agent:Agent, req: ChatCompletionRequest,model_instance:ModelInstance) -> None:
        """构建微调参数"""
        model_parameters = {}
        if agent.agent_parameters:
            for key, value in agent.agent_parameters.items():
                model_parameters[key] = value
        if "temperature" in model_parameters:
            req.temperature=model_parameters["temperature"]
        if "top_p" in model_parameters:
            req.top_p=model_parameters["top_p"]
        if "frequency_penalty" in model_parameters:
            req.frequency_penalty=model_parameters["frequency_penalty"]
        if "presence_penalty" in model_parameters:
            req.presence_penalty=model_parameters["presence_penalty"]
        if "max_tokens" in model_parameters:
            req.max_completion_tokens=model_parameters["max_tokens"]
        if "max_tokens" in model_parameters:
            req.max_tokens=model_parameters["max_tokens"]

        if "api_base" in model_parameters:
            model_instance.provider.provider_credential.credentials["api_base"] = model_parameters["api_base"]
        if "api_key" in model_parameters:
            model_instance.provider.provider_credential.credentials["api_key"] = model_parameters["api_key"]

    def _create_agent_runtime_config(self, agent:Agent):
        """创建AgentRuntimeConfig实例"""
        from runtime.tool.base.tool import Tool
        agent_tools: list[Tool] = []
        if agent.tools and len(agent.tools) > 0:
            for tool in agent.tools:
                agent_tool = AgentTool.model_validate(tool)
                if agent_tool.tool_provider_type==ToolProviderType.BUILTIN:
                    from runtime.tool.builtin_tool.tool_provider import BuiltinToolController
                    agent_tools.extend(BuiltinToolController().get_tools())
                elif agent_tool.tool_provider_type==ToolProviderType.MCP:
                    from runtime.tool.mcp.tool_provider import McpToolController
                    with get_db() as session:
                        from models import ToolInfo
                        tool_info:ToolInfo = session.query(ToolInfo).filter(ToolInfo.id == int(tool_info.id)).first()
                        if tool_info:
                            mcp_server:McpServer = session.query(McpServer).filter(
                                McpServer.server_code == tool_info.mcp_server_code).first()
                            agent_tools.extend(McpToolController(server_url=mcp_server.server_url).get_tools())
        return AgentRuntimeConfig(
            agent=agent,
            tools=agent_tools
        )

    async def _generate_tool_response(self, agent_runtime_config, user_message):
        """使用工具生成响应"""
        try:
            tool_args = LLMGenerator.choice_tool_invoke(agent_runtime_config.tools, user_message)
            tool_name = tool_args.get("tool_name")
            if not tool_name:
                # 提取<tool_response>...</tool_response>中的内容作为最终响应
                import re
                match = re.search(r"<tool_response>(.*?)</tool_response>", user_message, re.DOTALL)
                if match:
                    return match.group(1).strip()
                return ""

            tool_arguments = tool_args.get("tool_arguments", {})
            # 用字典加速查找，避免循环嵌套
            tool_map = {tool.entity.name: tool for tool in agent_runtime_config.tools}
            tool = tool_map.get(tool_name)
            if tool:
                tool_invoke_result = tool.invoke(tool_arguments)
                result:ToolInvokeResult = next(tool_invoke_result)
                if result.success:
                    new_tools:list[Tool] = [tool for tool in agent_runtime_config.tools if tool.entity.name != tool_name]
                    return await self._generate_tool_response(AgentRuntimeConfig(
                        agent=agent_runtime_config.agent, tools=new_tools
                    ), user_message+"\n<tool_response>\n"+str(result.data)+"\n</tool_response>")
            return ""
        except Exception as e:
            logger.error(f"Error generating tool response: {e}")
            raise


class AgentMessageRecordCallback(Callback):
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
        # ConversationMessageService.add_conversation_message(
        #     conversation_message
        # )
        self.user_message = content
        from event.event_manager import event_manager_context

        event_manager = event_manager_context.get()
        # from concurrent import futures
        # with futures.ThreadPoolExecutor() as executor:
        #     executor.submit(event_manager.emit, event="qa_rag_from_conversation_message", message=conversation_message)

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

        # remove <think> and </think> including the content between them
        import re

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
        # ConversationMessageService.add_conversation_message(
        #     message
        # )
        # import time
        # # 更新消息并添加到内存
        # self.agent_manager.get_or_create_memory(self.agent_id, self.session_id).add_interaction(Message(
        #     id=message_id,
        #     user_message=self.user_message if hasattr(self, 'user_message') else "",
        #     assistant_message=message_content,
        #     prev_message_id=ConversationMessageService.get_prev_message_id(agent_id=self.agent_id, session_id=self.session_id, message_id=message_id),
        #     meta={"timestamp": time.time()}
        # ))
        from event.event_manager import event_manager_context

        event_manager = event_manager_context.get()
        # from concurrent import futures
        # with futures.ThreadPoolExecutor() as executor:
        #     executor.submit(event_manager.emit, event="qa_rag_from_conversation_message", message=conversation_message)

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

    def __init__(self, agent: Agent, session_id: str, agent_manager: AgentManager):
        self.user_message = ""
        self.agent = agent
        self.session_id = session_id
        self.agent_manager = agent_manager
