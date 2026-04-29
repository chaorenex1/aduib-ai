import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any, Optional, Union

from component.storage.base_storage import storage_manager
from models import Agent, get_db
from runtime.agent.adapters import RequestAdapter, ResponseTextExtractor, ToolCallAdapter
from runtime.agent.agent_type import AgentExecutionContext
from runtime.agent.buffered_stream_response import BufferedStreamResponse
from runtime.agent.memory.prompt_markup import (
    build_memory_prompt_block,
    extract_selected_memory_ids_from_prompt,
    extract_used_memory_ids,
    sanitize_memory_markup,
)
from runtime.agent.memory_manager import MemoryManager
from runtime.agent.response_generator import ResponseGenerator
from runtime.agent.session_manager import SessionManager
from runtime.callbacks.base_callback import Callback
from runtime.callbacks.message_record_callback import MessageRecordCallback
from runtime.entities import (
    AnthropicMessage,
    AnthropicMessageRequest,
    AnthropicMessageResponse,
    AnthropicStreamEvent,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    PromptMessage,
    PromptMessageFunction,
    ResponseOutput,
    ResponseRequest,
    ResponseStreamEvent,
)
from runtime.entities.llm_entities import ChatCompletionRequest, LLMRequest, LLMResponse, LLMStreamResponse
from runtime.entities.message_entities import ThinkingOptions
from runtime.memory.manager import LegacyMemoryWriteDisabledError
from runtime.memory.types import MemorySignalType
from runtime.model_execution import AiModel
from runtime.model_manager import ModelManager
from runtime.protocol._openai_anthropic import StreamingToolCallCollector
from runtime.protocol._openai_responses import ResponsesStreamingToolCallCollector
from runtime.tool.base.tool import Tool
from runtime.tool.entities import ToolInvokeParams, ToolInvokeResult
from runtime.tool.tool_manager import ToolManager

logger = logging.getLogger(__name__)
SUPERVISOR_AGENT_NAME = "supervisor_agent_v3"


class AgentManager:
    """Main agent manager coordinating all components"""

    def __init__(
        self,
        agent_id: Optional[str] = "",
        auto_manage_context: bool = True,
        *,
        agent: Optional["Agent"] = None,
    ):
        self.auto_manage_context = auto_manage_context
        if agent is not None:
            self.agent: Agent = agent
        elif agent_id is not None:
            self.agent: Agent = self.get_agent(agent_id)
        else:
            raise ValueError("Either agent_id or agent must be provided")
        self.storage = storage_manager
        self.model_manager = ModelManager()
        self.session_manager = SessionManager()
        self.memory_manager = MemoryManager(self.agent)
        self.tool_manager = ToolManager()
        self.tools = self.get_agent_tools(self.agent)
        self.response_generator = ResponseGenerator(self.model_manager, self._build_response_callbacks)
        self.tool_collector_cache: dict[
            str, Union[StreamingToolCallCollector, ResponsesStreamingToolCallCollector]
        ] = {}

    def _build_response_callbacks(self, agent: Agent) -> list[Callback]:
        return [
            MessageRecordCallback(),
            AgentMessageRecordCallback(
                agent=agent,
                agent_manager=self,
            ),
        ]

    async def arun_response(
        self,
        request: LLMRequest,
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamResponse, None]]:
        """Entry point for processing an agent request and generating a response."""
        user_id: Optional[str] = None
        try:
            from libs.context import get_current_user_id

            user_id = get_current_user_id()
        except Exception:
            pass
        ctx: AgentExecutionContext = self._build_agent_execution_context(user_id=user_id)

        self.inject_agent_system_prompt(request)
        self._apply_agent_request_overrides(request)
        await self.inject_memory_into_user_prompt(request, ctx)

        # Inject tools into request (protocol-aware, in-place)
        self.add_tools_to_request(request)

        raw_response = await self.arun_agent_loop(request, ctx=ctx)

        return raw_response

    def inject_agent_system_prompt(self, request: LLMRequest) -> None:
        prompt_template = str(getattr(self.agent, "prompt_template", "") or "").strip()
        if not prompt_template:
            return
        RequestAdapter(request).prepend_system_prompt(prompt_template)

    def _apply_agent_request_overrides(self, request: LLMRequest) -> None:
        if not self._is_supervisor_agent():
            return
        self._force_thinking_mode(request)

    def _is_supervisor_agent(self) -> bool:
        agent_name = str(getattr(self.agent, "name", "") or "").strip().lower()
        return agent_name == SUPERVISOR_AGENT_NAME

    def _force_thinking_mode(self, request: LLMRequest) -> None:
        forced_budget = self._parse_positive_int(
            self.agent.agent_parameters.get("thinking_budget") or self.agent.agent_parameters.get("budget_tokens")
        )
        if isinstance(request, ChatCompletionRequest):
            request.include_reasoning = True
            request.enable_thinking = True
            if forced_budget and request.thinking_budget is None:
                request.thinking_budget = forced_budget
            if request.thinking is None:
                request.thinking = ThinkingOptions(type="enabled", budget_tokens=forced_budget)
            else:
                if not getattr(request.thinking, "type", None):
                    request.thinking.type = "enabled"
                if forced_budget and getattr(request.thinking, "budget_tokens", None) is None:
                    request.thinking.budget_tokens = forced_budget
            return

        if isinstance(request, AnthropicMessageRequest):
            if request.thinking is None:
                request.thinking = ThinkingOptions(type="adaptive", budget_tokens=forced_budget)
                from runtime.entities.anthropic_entities import AnthropicOutputConfig

                request.output_config = AnthropicOutputConfig(effort="high")
            else:
                if not getattr(request.thinking, "type", None):
                    request.thinking.type = "enabled"
                if forced_budget and getattr(request.thinking, "budget_tokens", None) is None:
                    request.thinking.budget_tokens = forced_budget

    @staticmethod
    def _parse_positive_int(value: object) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    async def arun_agent_loop(self, request: LLMRequest, *, ctx: AgentExecutionContext) -> Any:
        max_rounds = ctx.agent.agent_parameters.get("max_tool_rounds", 20)

        current_request = request.model_copy()

        last_response = await self.response_generator.generate_response(
            self.agent,
            ctx,
            current_request,
        )

        tool_calls: list[ToolInvokeParams] = []
        buffered_response: Optional[BufferedStreamResponse] = None
        if current_request.stream:
            buffered_response = await self.buffer_stream_response(
                ctx,
                current_request,
                last_response,
            )
            last_response = self.replay_stream_response(buffered_response.events)
            tool_calls = buffered_response.tool_calls
        else:
            tool_calls = self.convert_response_to_tools(last_response)
        logger.info(
            "[OODA] round=%d/%d tool_calls=%d",
            ctx.ooda_round,
            max_rounds,
            len(tool_calls) if tool_calls else 0,
        )

        if not tool_calls or len(tool_calls) == 0:
            return last_response

        tool_results: list[ToolInvokeResult] = await self._execute_tool_calls(
            tool_calls, ctx=ctx, request=current_request, last_response=last_response
        )
        self.add_tool_results_to_request(tool_results, current_request)

        next_response = await self.response_generator.generate_response(
            self.agent,
            ctx,
            current_request,
        )
        next_buffered_response: Optional[BufferedStreamResponse] = None
        if current_request.stream:
            next_buffered_response = await self.buffer_stream_response(
                ctx,
                current_request,
                next_response,
                include_tool_calls=False,
            )
            last_response = self.replay_stream_response(next_buffered_response.events)
        else:
            last_response = next_response

        # Increment round counter before recursive call
        ctx.ooda_round += 1

        # Check if max rounds already reached (for recursive calls)
        if ctx.ooda_round > max_rounds:
            logger.warning("[OODA] max rounds %d reached, returning last response", max_rounds)
            return last_response

        if current_request.stream:
            if next_buffered_response and next_buffered_response.text:
                self.add_assistant_content_to_request(current_request, next_buffered_response.text)
        else:
            self.add_assistant_message_to_request(current_request, last_response)

        self.add_tools_to_request(current_request)

        # Recursive call with updated counter
        last_response = await self.arun_agent_loop(current_request, ctx=ctx)

        return last_response

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolInvokeParams],
        *,
        ctx: AgentExecutionContext,
        request: LLMRequest,
        last_response: LLMResponse,
    ) -> list:
        """Execute native tool_calls from LLM response, return ToolPromptMessage list."""

        results: list[ToolInvokeResult] = []
        for call in tool_calls:
            name: str = call.name
            args = json.loads(call.arguments)
            args["session_id"] = ctx.session_id
            args["agent_id"] = ctx.agent_id
            args["user_id"] = ctx.user_id
            args["agent_manager"] = self
            provider_type = call.tool_provider

            result = await self.tool_manager.invoke_tool(
                tool_name=name,
                tool_arguments=args,
                tool_provider=provider_type,
                tool_call_id=call.tool_call_id,
                message_id=call.message_id,
            )
            results.append(result)
        return results

    def cleanup_memory(self) -> None:
        """Clean up memory for a session"""
        # Legacy cleanup would delegate to async long-term memory deletion through
        # AgentMemory.clear_memory(); keep the old path blocked until migrated.
        # self.memory_manager.cleanup_memory()
        raise LegacyMemoryWriteDisabledError(
            "AgentManager.cleanup_memory() is disabled until legacy long-term memory cleanup is migrated."
        )

    @staticmethod
    def extract_response_text(raw_response: LLMResponse) -> str:
        """Extract response text from LLM response."""
        return ResponseTextExtractor.from_response(raw_response)

    async def _summarize_interaction(self, full_response: str) -> str:
        try:
            from runtime.generator.generator import LLMGenerator

            return await LLMGenerator.generate_memory_interaction_summary(
                full_message=full_response,
                model_name=self.agent.model_id,
            )
        except Exception as ex:
            logger.warning("Summarize interaction failed: %s", ex)
            return full_response

    async def manage_post_response_memory(
        self, session_id: str, user_message: str, response_text: str, last_response: bool = False
    ) -> None:
        try:
            await self.memory_manager.add_memory("User: " + user_message, long_term_memory=False)
            await self.memory_manager.add_memory("Assistant: " + response_text, long_term_memory=False)

            if last_response:
                from service import ConversationMessageService, ModelService

                model = ModelService.get_model_by_id(int(self.agent.model_id))
                current_length = ConversationMessageService.get_context_length(self.agent.id, session_id)
                remaining_ratio = 1.0 - (current_length / model.max_tokens) if model and model.max_tokens else 1.0
                if remaining_ratio <= 0.1:
                    if self.session_manager.inactivate_session(session_id):
                        full_response_text: str = await self.memory_manager.get_full_response_text()
                        summary = await self._summarize_interaction(full_response_text)
                        await self.memory_manager.clear_short_term_memory()
                        # short term compact session
                        await self.memory_manager.add_memory(summary, long_term_memory=False, compact_session=True)
                        # long term memory
                        if self.agent.enabled_memory != 1:
                            return
                        # Legacy long-term writes used runtime.memory.manager.store(); keep
                        # the old path blocked until this caller is migrated.
                        # await self.memory_manager.add_memory(
                        #     response_text, long_term_memory=True, compact_session=True
                        # )
                        raise LegacyMemoryWriteDisabledError(
                            "AgentManager long-term post-response memory writes are disabled until migrated "
                            "to the new memory pipeline."
                        )
                        logger.info("Memory compacted for session %s due to context length.", session_id)
        except LegacyMemoryWriteDisabledError:
            raise
        except Exception as ex:
            logger.warning("Post-response memory management failed: %s", ex)

    def _build_agent_execution_context(self, user_id: str) -> AgentExecutionContext:
        """Build AgentExecutionContext from AgentInput"""
        # Get or create session
        session_id = self.session_manager.create_session(self.agent, user_id=user_id)
        # Get memory
        memory = self.memory_manager.get_or_create_memory(session_id)
        return AgentExecutionContext(
            agent=self.agent, agent_id=self.agent.id, user_id=user_id, session_id=session_id, memory=memory
        )

    async def inject_memory_into_user_prompt(self, request: LLMRequest, ctx: AgentExecutionContext) -> None:
        user_prompt = self.get_latest_user_prompt_text(request)
        if not user_prompt.strip():
            return

        try:
            context = await ctx.memory.retrieve_context(
                user_prompt,
                long_term_memory=self.agent.enabled_memory != 1 or ctx.memory is None,
                compact_session=True,
            )
            short_term_memory = context.get("short_term", "")

            # Handle compact session memory (direct string from Redis)
            if short_term_memory and isinstance(short_term_memory, str):
                memory_block = self._build_compact_memory_block(short_term_memory)
                if memory_block:
                    self.append_memory_block_to_latest_user_prompt(request, memory_block)
                return

            # Handle long-term memory with embeddings
            long_term_memories = context.get("long_term", [])
            if not long_term_memories:
                return

            from service.learning_signal_service import LearningSignalService

            await LearningSignalService.emit_memory_signals(
                user_id=str(ctx.user_id or self.agent.user_id or self.agent.id),
                signal_type=MemorySignalType.MEMORY_SELECTED,
                memory_ids=[memory.memory_id for memory in long_term_memories],
                value_by_source={memory.memory_id: float(memory.score or 0.0) for memory in long_term_memories},
                context={"session_id": str(ctx.session_id), "source": "agent_user_prompt"},
            )

            memory_block = build_memory_prompt_block(long_term_memories)
            if memory_block:
                self.append_memory_block_to_latest_user_prompt(request, memory_block)
        except RuntimeError:
            raise
        except Exception:
            logger.warning("Failed to inject memory into user prompt", exc_info=True)

    @staticmethod
    def _build_compact_memory_block(compact_session: str) -> str:
        """Build a prompt block for compact session memory (direct injection)."""
        if not compact_session:
            return ""
        return (
            "<system-reminder-compact-session>\n"
            f"Session Summary:\n{compact_session}\n"
            "</system-reminder-compact-session>"
        )

    def get_or_create_tool_collector(
        self, session_id: str, request: LLMRequest
    ) -> Union[StreamingToolCallCollector, ResponsesStreamingToolCallCollector]:
        if session_id in self.tool_collector_cache:
            return self.tool_collector_cache[session_id]
        else:
            if isinstance(request, (ChatCompletionRequest, ResponseRequest)):
                self.tool_collector_cache[session_id] = ResponsesStreamingToolCallCollector()
            elif isinstance(request, AnthropicMessageRequest):
                self.tool_collector_cache[session_id] = StreamingToolCallCollector()
        return self.tool_collector_cache[session_id]

    def get_agent(self, agent_id: str) -> Agent:
        """Fetch agent from storage by ID"""
        # Get agent
        agent: Agent
        if agent_id is not None:
            with get_db() as db:
                    agent = db.query(Agent).filter(Agent.name == agent_id).first()
                    if not agent:
                        raise ValueError(f"Agent with id or name '{agent_id}' not found")
        else:
            raise ValueError("agent_id is required in the request")
        return agent

    def get_agent_tools(self, agent: Agent) -> list[Tool]:
        """Fetch tools from storage by ID"""
        tools: list[Tool] = []
        if agent.tools:
            for tool_meta in agent.tools:
                tool_name: str = tool_meta.get("tool_name", "")
                tool_provider_type = tool_meta.get("tool_provider_type", "")
                tool: Tool = self.tool_manager.get_tool_provider(tool_provider_type).get_tool(
                    tool_name
                )  # Validate tool exists
                if tool:
                    tools.append(tool)
        return tools

    @staticmethod
    def content_to_text(content: object) -> str:
        return ResponseTextExtractor.flatten_content(content)

    def get_latest_user_prompt_text(self, request: LLMRequest) -> str:
        return RequestAdapter(request).latest_user_text()

    def append_memory_block_to_latest_user_prompt(self, request: LLMRequest, memory_block: str) -> None:
        RequestAdapter(request).append_memory_block_to_latest_user(memory_block)

    def add_tools_to_request(self, request: LLMRequest) -> None:
        """Inject self.tools into request in protocol-correct format (in-place).
        CompletionRequest has no tools field and is silently skipped.
        """
        RequestAdapter(request).ensure_tools(self.tools)

    @staticmethod
    def _log_background_memory_task(task: asyncio.Task[object]) -> None:
        try:
            task.result()
        except Exception as ex:
            logger.warning("Background memory write failed: %s", ex)

    def _schedule_tool_result_memory_write(self, content: str) -> None:
        task = asyncio.create_task(
            self.memory_manager.add_memory("Tool Result: " + content, long_term_memory=False)
        )
        task.add_done_callback(self._log_background_memory_task)

    @staticmethod
    def ensure_response_input_list(request: ResponseRequest) -> list:
        return RequestAdapter.ensure_response_input_list(request)

    @staticmethod
    def normalize_response_output_to_input_items(response: ResponseOutput | list[object]) -> list:
        return RequestAdapter.normalize_response_output_to_input_items(response)

    def add_tool_results_to_request(self, tool_results: list[ToolInvokeResult], request: LLMRequest) -> None:
        """Add tool results to request for next round of LLM processing"""
        if not tool_results:
            return
        for tool_result in tool_results:
            if isinstance(request, ChatCompletionRequest):
                from runtime.entities import TextPromptMessageContent, ToolPromptMessage

                content_list: list[TextPromptMessageContent] = [
                    TextPromptMessageContent(
                        text=f"Tool {tool_result.name} called status: {tool_result.success}",
                    )
                ]
                if tool_result.success:
                    content_list.append(TextPromptMessageContent(text=tool_result.to_normal()))
                else:
                    content_list.append(TextPromptMessageContent(text=f"Error: {tool_result.error}"))
                request.messages.append(ToolPromptMessage(tool_call_id=tool_result.tool_call_id, content=content_list))

                self._schedule_tool_result_memory_write(self.content_to_text(content_list))
            elif isinstance(request, AnthropicMessageRequest):
                from runtime.entities import AnthropicTextBlock, AnthropicToolResultBlock

                content_list: list[AnthropicTextBlock] = [
                    AnthropicTextBlock(
                        text=f"Tool {tool_result.name} called status: {tool_result.success}",
                    )
                ]
                if tool_result.success:
                    content_list.append(AnthropicTextBlock(text=tool_result.to_normal()))
                else:
                    content_list.append(AnthropicTextBlock(text=f"Error: {tool_result.error}"))
                request.messages.append(
                    AnthropicMessage(
                        role="assistant",
                        content=[
                            AnthropicToolResultBlock(
                                tool_use_id=tool_result.tool_call_id,
                                content=content_list,
                                is_error=tool_result.success,
                            )
                        ],
                    )
                )

                self._schedule_tool_result_memory_write(self.content_to_text(content_list))
            elif isinstance(request, ResponseRequest):
                from runtime.entities import ResponseInputItem, ResponseOutputFunctionCallOutput

                content: str = f"Tool {tool_result.name} called status: {tool_result.success}"
                if tool_result.success:
                    content += f"\n{tool_result.to_normal()}"
                else:
                    content += f"\n{tool_result.error}"
                self.ensure_response_input_list(request).append(
                    ResponseInputItem(
                        role="assistant",
                        content=[ResponseOutputFunctionCallOutput(call_id=tool_result.tool_call_id, output=content)],
                    )
                )

                self._schedule_tool_result_memory_write(content)

    def convert_response_to_tools(self, response: LLMResponse) -> list[ToolInvokeParams]:
        """Convert response to Tools"""
        return ToolCallAdapter(self.tool_manager).from_response(response)

    async def convert_stream_response_to_tools(
        self, ctx: AgentExecutionContext, request: LLMRequest, response: LLMStreamResponse
    ) -> list[ToolInvokeParams]:
        """Convert response to Tools"""
        tool_collector = self.get_or_create_tool_collector(str(ctx.session_id), request)
        return await ToolCallAdapter(self.tool_manager).from_stream(response, tool_collector)

    @staticmethod
    async def replay_stream_response(
        events: list[ResponseStreamEvent | ChatCompletionResponseChunk | AnthropicStreamEvent],
    ) -> AsyncGenerator[ResponseStreamEvent | ChatCompletionResponseChunk | AnthropicStreamEvent, None]:
        for event in events:
            if hasattr(event, "model_copy"):
                yield event.model_copy(deep=True)
            else:
                yield event

    async def buffer_stream_response(
        self,
        ctx: AgentExecutionContext,
        request: LLMRequest,
        response: LLMStreamResponse,
        *,
        include_tool_calls: bool = True,
    ) -> BufferedStreamResponse:
        buffered = BufferedStreamResponse()
        if not isinstance(response, AsyncGenerator):
            return buffered

        async for event in response:
            buffered.events.append(event)

        if include_tool_calls and buffered.events:
            buffered.tool_calls = await self.convert_stream_response_to_tools(
                ctx,
                request,
                self.replay_stream_response(buffered.events),
            )

        if buffered.events:
            buffered.text = await self.extract_stream_response_text(
                self.replay_stream_response(buffered.events),
            )

        return buffered

    async def add_stream_assistant_message_to_request(self, current_request: LLMRequest, response: LLMStreamResponse):
        """Add assistant message to request from stream response"""
        if not isinstance(response, AsyncGenerator):
            return

        content_text = await self.extract_stream_response_text(response)
        if not content_text:
            return
        RequestAdapter(current_request).append_assistant_text(content_text)

    @staticmethod
    async def extract_stream_response_text(
        response: AsyncGenerator[ResponseStreamEvent | ChatCompletionResponseChunk | AnthropicStreamEvent, None],
    ) -> str:
        return await ResponseTextExtractor.from_stream(response)

    def add_assistant_message_to_request(self, current_request: LLMRequest, response: LLMResponse):
        """Add assistant message to request from non-stream response"""
        RequestAdapter(current_request).append_assistant_response(response)

    def add_assistant_content_to_request(self, current_request: LLMRequest, content: str):
        """Add assistant message content to request from non-stream response"""
        RequestAdapter(current_request).append_assistant_text(content)

    def add_user_message_to_request(self, current_request: LLMRequest, user_prompt: str):
        """Add user message to request"""
        RequestAdapter(current_request).append_user_text(user_prompt)


class AgentMessageRecordCallback(Callback):
    """Callback for recording agent messages"""

    def __init__(self, agent: Agent, agent_manager: AgentManager, ctx: AgentExecutionContext):
        self.user_message = ""
        self.agent = agent
        self.agent_manager = agent_manager
        self.ctx = ctx

    @staticmethod
    def _extract_user_message(prompt_messages: Union[list[PromptMessage], str]) -> str:
        if isinstance(prompt_messages, str):
            return sanitize_memory_markup(prompt_messages)
        if not isinstance(prompt_messages, list):
            return ""

        for message in reversed(prompt_messages):
            role = getattr(getattr(message, "role", None), "value", None) or getattr(message, "role", None)
            if role != "user":
                continue
            return sanitize_memory_markup(ResponseTextExtractor.flatten_content(getattr(message, "content", None)))
        return ""

    @staticmethod
    def _set_response_text(result: LLMResponse, content: str) -> None:
        from runtime.entities import AnthropicTextBlock
        from runtime.entities.response_entities import ResponseOutputMessage, TextContentBlock

        if isinstance(result, ChatCompletionResponse):
            if result.message is not None:
                result.message.content = content
            return
        if isinstance(result, AnthropicMessageResponse):
            result.content = [AnthropicTextBlock(text=content)]
            return
        if isinstance(result, ResponseOutput):
            for item in result.output:
                if isinstance(item, ResponseOutputMessage):
                    item.content = [TextContentBlock(text=content)]
                    return

    @staticmethod
    def _log_task_exception(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except Exception as ex:
            logger.warning("Post-response memory task failed: %s", ex)

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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        self.user_message = self._extract_user_message(prompt_messages)

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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        if agent_session_id is None:
            return

        response_text = self.agent_manager.extract_response_text(result)
        response_text, used_memory_ids = extract_used_memory_ids(response_text)
        self._set_response_text(result, response_text)
        if not self.user_message and not response_text:
            return

        selected_memory_ids: list[str] = []
        for prompt_message in prompt_messages:
            selected_memory_ids.extend(
                extract_selected_memory_ids_from_prompt(
                    self.agent_manager.content_to_text(getattr(prompt_message, "content", None))
                )
            )
        selected_memory_id_set = set(selected_memory_ids)
        adopted_memory_ids = [memory_id for memory_id in used_memory_ids if memory_id in selected_memory_id_set]

        if adopted_memory_ids:

            async def _emit_used_memory_signals() -> None:
                from service.learning_signal_service import LearningSignalService

                signal_context = {
                    "session_id": str(agent_session_id),
                    "user_message": self.user_message[:200],
                    "response_length": len(response_text),
                }
                await LearningSignalService.emit_memory_signals(
                    user_id=str(user or self.agent.user_id or self.agent.id),
                    signal_type=MemorySignalType.MEMORY_USED_IN_ANSWER,
                    memory_ids=adopted_memory_ids,
                    context=signal_context,
                )
                await LearningSignalService.emit_memory_signals(
                    user_id=str(user or self.agent.user_id or self.agent.id),
                    signal_type=MemorySignalType.MEMORY_ADOPTION,
                    memory_ids=adopted_memory_ids,
                    context={**signal_context, "derived_from": MemorySignalType.MEMORY_USED_IN_ANSWER.value},
                    value=1.0,
                )

            signal_task = asyncio.create_task(_emit_used_memory_signals())
            signal_task.add_done_callback(self._log_task_exception)

        task = asyncio.create_task(
            self.agent_manager.manage_post_response_memory(
                str(agent_session_id),
                self.user_message,
                response_text,
                last_response=not tools
                or self.ctx.ooda_round == self.ctx.agent.agent_parameters.get("max_tool_rounds"),
            )
        )
        task.add_done_callback(self._log_task_exception)

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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        pass
