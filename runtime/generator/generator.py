import json
import logging
import re
from typing import Any, Optional, cast

from runtime.entities import (
    ChatCompletionResponse,
    PromptMessage,
    PromptMessageRole,
    SystemPromptMessage,
    UserPromptMessage,
)
from runtime.entities.document_entities import Document
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.model_entities import ModelType
from runtime.generator.prompts import (
    ANSWER_INSTRUCTION_FROM_KNOWLEDGE,
    BLOG_RESEARCH_PROMPT,
    BLOG_TRANSFORM_PROMPT,
    CONVERSATION_TITLE_PROMPT,
    GENERATOR_QA_PROMPT,
    LEARNING_PARAM_OPTIMIZE_PROMPT,
    MEMORY_CLASSIFICATION_PROMPT,
    MEMORY_DOMAIN_PROMPT,
    MEMORY_FORMAT_PROMPT,
    MEMORY_FORMAT_USER_PROMPT,
    MEMORY_INSIGHT_DISTILL_PROMPT,
    MEMORY_REACT_PLANNER_PROMPT,
    MEMORY_RELEVANCE_JUDGE_PROMPT,
    MEMORY_TOPIC_MERGE_JUDGE_PROMPT,
    MEMORY_TOPIC_PROMPT,
    MEMORY_TYPE_PROMPT,
    SESSION_CONTINUITY_SUMMARY_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_STRUCTURED_OUTPUT_GENERATE,
    TAG_STRUCTURED_OUTPUT_PROMPT,
    TASK_GRADE_PROMPT,
    TOOL_SELECTION_PROMPT,
    TRIPLES_PROMPT,
    TOOL_CHiOCE_PROMPT,
)
from runtime.model_manager import ModelManager
from runtime.tool.base.tool import Tool

logger = logging.getLogger(__name__)


class LLMGenerator:
    @classmethod
    def generate_conversation_name(cls, query):
        cleaned_answer, query = cls._generate_conversation_name(query)
        if cleaned_answer is None:
            return ""
        language = "chinese"
        try:
            result_dict = json.loads(cleaned_answer)
            answer = result_dict["Your Output"]
            language = result_dict["Language Type"]
        except json.JSONDecodeError:
            logger.exception("Failed to generate name after answer, use query instead")
            answer = query
        name = answer.strip()

        if len(name) > 75:
            name = name[:75] + "..."

        return name, language

    @classmethod
    def _generate_conversation_name(cls, query):
        prompt = CONVERSATION_TITLE_PROMPT
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")
        prompt += query + "\n"
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [UserPromptMessage(role=PromptMessageRole.USER, content=prompt)]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        cleaned_answer = re.sub(r"^.*(\{.*\}).*$", r"\1", answer, flags=re.DOTALL)
        return cleaned_answer, query

    @classmethod
    def generate_summary(cls, query):
        prompt = SUMMARY_PROMPT
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")
        # prompt += query + "\n"
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=prompt),
            UserPromptMessage(role=PromptMessageRole.USER, content=query),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

    @classmethod
    async def generate_memory_interaction_summary(
        cls,
        full_message: str,
        model_name: Optional[str] = None,
    ) -> str:
        model_manager = ModelManager()
        if model_name:
            model_instance = model_manager.get_model_instance(model_name=model_name)
        else:
            model_instance = None
        if model_instance is None:
            model_instance = model_manager.get_default_model_instance(
                model_type=ModelType.LLM.to_model_type(),
            )
        if model_instance is None:
            raise ValueError("No model instance available for memory interaction summary")

        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=SESSION_CONTINUITY_SUMMARY_PROMPT),
            UserPromptMessage(
                role=PromptMessageRole.USER,
                content=(f"<conversation_message>\n{full_message}\n</conversation_message>\n\n"),
            ),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.1,
            stream=False,
        )
        response: ChatCompletionResponse = await model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer.strip()

    @classmethod
    def generate_qa_document(cls, query: str, document_language: str):
        prompt = GENERATOR_QA_PROMPT.format(language=document_language)

        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )

        prompt_messages: list[PromptMessage] = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=prompt),
            UserPromptMessage(role=PromptMessageRole.USER, content=query),
        ]

        # Explicitly use the non-streaming overload
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer.strip()

    @classmethod
    def generate_language(cls, query):
        cleaned_answer, query = cls._generate_conversation_name(query)
        if cleaned_answer is None:
            return ""
        try:
            result_dict = json.loads(cleaned_answer)
            answer = result_dict["Language Type"]
        except json.JSONDecodeError:
            logger.exception("Failed to generate name after answer, use query instead")
            answer = query
        name = answer.strip()

        if len(name) > 75:
            name = name[:75] + "..."

        return name

    @classmethod
    def generate_structured_output(cls, instruction: str):
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )

        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=SYSTEM_STRUCTURED_OUTPUT_GENERATE),
            UserPromptMessage(role=PromptMessageRole.USER, content=instruction),
        ]

        try:
            request = ChatCompletionRequest(
                model=model_instance.model,
                messages=prompt_messages,
                temperature=0.01,
                stream=False,
            )
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)

            raw_content = response.message.content

            if not isinstance(raw_content, str):
                raise ValueError(f"LLM response content must be a string, got: {type(raw_content)}")

            try:
                parsed_content = json.loads(raw_content)
            except json.JSONDecodeError:
                # Attempt to extract JSON from the response using regex
                json_match = re.search(r"(\{.*\}|\[.*\])", raw_content, re.DOTALL)
                if json_match:
                    try:
                        parsed_content = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        raise ValueError(f"Failed to parse JSON from LLM response: {raw_content}")
                else:
                    raise ValueError(f"No JSON object found in LLM response: {raw_content}")

            if not isinstance(parsed_content, dict | list):
                raise ValueError(f"Failed to parse structured output from llm: {raw_content}")

            generated_json_schema = json.dumps(parsed_content, indent=2, ensure_ascii=False)
            return {"output": generated_json_schema, "error": ""}

        except Exception as e:
            error = str(e)
            return {"output": "", "error": f"Failed to generate JSON Schema. Error: {error}"}

    @classmethod
    def generate_triples(cls, query: str):
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )

        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=TRIPLES_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=query),
        ]

        # Explicitly use the non-streaming overload
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer.strip()

    @classmethod
    def generate_retrieval_content(cls, query: str, results: list[Document], rag_type: str) -> str:
        question = query
        contexts: list[dict[str, Any]] = []
        if rag_type == "paragraph":
            for result in results:
                contexts.append({"doc_id": result.metadata.get("doc_id"), "content": result.content})
            context = json.dumps(contexts, ensure_ascii=False, indent=2)
        else:
            for result in results:
                contexts.append(
                    {
                        "doc_id": result.metadata.get("doc_id"),
                        "question": result.content,
                        "answer": result.metadata.get("answer"),
                    }
                )
            context = json.dumps(contexts, ensure_ascii=False, indent=2)
        prompt = ANSWER_INSTRUCTION_FROM_KNOWLEDGE.format(context=context, question=question)
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [UserPromptMessage(role=PromptMessageRole.USER, content=prompt)]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

    @classmethod
    def choice_tool_invoke(cls, tools: list[Tool], query: str) -> dict:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        _tools = "".join(
            "<tool>\n<name>"
            + tool.entity.name
            + "</name>\n<description>"
            + tool.entity.description
            + "</description>\n<arguments>"
            + json.dumps(tool.entity.parameters)
            + "</arguments>\n</tool>\n"
            for tool in tools
        )
        formatted_prompt = TOOL_CHiOCE_PROMPT.format(_tools=_tools)
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=formatted_prompt),
            UserPromptMessage(role=PromptMessageRole.USER, content=query),
        ]

        # Explicitly use the non-streaming overload
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        # search <tool_use>
        #   <name>...</name>
        #   <arguments>...</arguments>
        # </tool_use>
        match = re.search(
            r"<tool_use>\s*<name>(.*?)</name>\s*<arguments>(.*?)</arguments>\s*</tool_use>", answer, re.DOTALL
        )
        if match:
            tool_name = match.group(1).strip()
            tool_arguments_str = match.group(2).strip()
            try:
                tool_arguments = json.loads(tool_arguments_str)
            except json.JSONDecodeError:
                tool_arguments = {}
            return {"tool_name": tool_name, "tool_arguments": tool_arguments, "raw_response": answer}
        else:
            return {"tool_name": None, "tool_arguments": {}, "raw_response": answer}

    @classmethod
    def generate_content(cls, prompt: str, temperature: float = 0.7) -> str:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompt_messages = [
            UserPromptMessage(role=PromptMessageRole.USER, content=prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=temperature,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer.strip()

    @classmethod
    def generate_doc_research(cls, raw_content: str) -> str:
        prompt = BLOG_RESEARCH_PROMPT.format(raw_content=raw_content)
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [UserPromptMessage(role=PromptMessageRole.USER, content=prompt)]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

    @classmethod
    def generate_blog_transform(cls, raw_content: str) -> str:
        prompt = BLOG_TRANSFORM_PROMPT.format(raw_content=raw_content)
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [UserPromptMessage(role=PromptMessageRole.USER, content=prompt)]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

    @classmethod
    def grade_task(cls, prompt: str) -> str:
        from configs import config

        model_list = config.grade_model_list
        system_prompt = TASK_GRADE_PROMPT.replace("{model_list}", json.dumps(model_list, ensure_ascii=False, indent=2))
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=system_prompt),
            UserPromptMessage(role=PromptMessageRole.USER, content=prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.1,
            top_p=0.9,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

    @classmethod
    def generate_tags(cls, prompt: str) -> list[str]:
        system_prompt = TAG_STRUCTURED_OUTPUT_PROMPT
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompts = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=system_prompt),
            UserPromptMessage(role=PromptMessageRole.USER, content=prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.1,
            top_p=0.9,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content)
        try:
            return json.loads(answer)
        except json.JSONDecodeError:
            logger.exception("Failed to generate tags, return empty list")
        return []

    @classmethod
    def generate_memory_format(
        cls,
        mem_type: str,
        mem_domain: str,
        topic: str,
        segments: list[str],
        timestamp: str = "",
        operation: str = "create",
        existing_content: str = "",
    ) -> str:
        """将话题内容片段格式化为适合 RAG 检索的记忆文档。

        通过 LLM 推理选择最优格式，而非硬编码规则。
        失败时降级返回原始拼接文本。
        """
        segments_text = "\n".join(f"- {s.strip()}" for s in segments if s.strip())
        normalized_operation = "append" if operation == "append" else "create"
        user_prompt = MEMORY_FORMAT_USER_PROMPT.format(
            operation=normalized_operation,
            mem_type=mem_type,
            mem_domain=mem_domain,
            topic=topic,
            timestamp=timestamp or "N/A",
            existing_content=existing_content.strip() or "N/A",
            segments=segments_text or "- (none)",
        )
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_FORMAT_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=user_prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.3,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            return cast(str, response.message.content).strip()
        except Exception:
            logger.exception("generate_memory_format: LLM failed, falling back to raw join")
            if normalized_operation == "append" and existing_content.strip():
                appended_segments = "\n".join(s.strip() for s in segments if s.strip())
                if appended_segments:
                    return f"{existing_content.strip()}\n\n{appended_segments}"
                return existing_content.strip()
            return f"{topic}\n" + "\n".join(s.strip() for s in segments if s.strip())

    @classmethod
    def generate_memory_classification(cls, content: str) -> dict:
        """一次调用同时返回 type 和 domain，保证两者语义一致。

        Returns:
            {"type": str, "domain": str}，解析失败时返回默认值。
        """
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_CLASSIFICATION_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content).strip()
        result = json.loads(answer)
        return result

    @classmethod
    def generate_memory_type(cls, content: str) -> str:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_TYPE_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content).strip().lower()
        return answer

    @classmethod
    def generate_memory_domain(cls, content: str) -> str:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_DOMAIN_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content).strip().lower()
        return answer

    @classmethod
    def generate_memory_topic(cls, content: str, json_schema: str) -> str:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        system_prompt = MEMORY_TOPIC_PROMPT.format(json_schema=json_schema)
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=system_prompt),
            UserPromptMessage(role=PromptMessageRole.USER, content=content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.1,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content).strip()
        return answer

    @classmethod
    def plan_memory_react_action(cls, context: str, state: dict[str, Any]) -> dict[str, Any]:
        """为记忆检索 ReAct loop 规划下一步动作。"""
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(model_type=ModelType.LLM.to_model_type())
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_REACT_PLANNER_PROMPT),
            UserPromptMessage(
                role=PromptMessageRole.USER,
                content=f"Context:\n{context}\n\nState:\n{json.dumps(state, ensure_ascii=False, indent=2)}",
            ),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            answer = cast(str, response.message.content).strip()
            raw = re.search(r"\{.*\}", answer, re.DOTALL)
            plan = json.loads(raw.group() if raw else answer)
            if not isinstance(plan, dict):
                raise ValueError("planner output is not an object")
            action = str(plan.get("action") or "").strip().lower()
            if action not in {"search", "expand", "stop"}:
                raise ValueError(f"unsupported action: {action}")
            query = str(plan.get("query") or "").strip()
            filters = plan.get("filters") if isinstance(plan.get("filters"), dict) else {}
            retrieval_method = str(plan.get("retrieval_method") or "").strip().lower()
            if retrieval_method and retrieval_method not in {"semantics", "full_text", "vector"}:
                raise ValueError(f"unsupported retrieval_method: {retrieval_method}")
            weights = plan.get("weights") if isinstance(plan.get("weights"), dict) else {}
            score_threshold = plan.get("score_threshold")
            memory_ids = [str(mid) for mid in plan.get("memory_ids", []) if mid]
            if action == "search" and not query:
                raise ValueError("search action requires query")
            if action == "expand" and not memory_ids:
                raise ValueError("expand action requires memory_ids")
            if action != "search":
                retrieval_method = ""
                weights = {}
                score_threshold = None
            if weights:
                cleaned_weights: dict[str, float] = {}
                for key in ("keyword_weight", "vector_weight"):
                    if key in weights:
                        cleaned_weights[key] = float(weights[key])
                weights = cleaned_weights
            if score_threshold is not None:
                score_threshold = float(score_threshold)
            return {
                "action": action,
                "query": query,
                "filters": filters,
                "retrieval_method": retrieval_method,
                "weights": weights,
                "score_threshold": score_threshold,
                "memory_ids": memory_ids[:5],
                "reason_summary": str(plan.get("reason_summary") or "").strip(),
            }
        except Exception:
            logger.exception("plan_memory_react_action: failed, falling back to stop")
            return {
                "action": "stop",
                "query": "",
                "filters": {},
                "retrieval_method": "",
                "weights": {},
                "score_threshold": None,
                "memory_ids": [],
                "reason_summary": "planner_error",
            }

    @classmethod
    def judge_memory_relevance(cls, context: str, candidates: list[dict]) -> list[str]:
        """裁决候选记忆与当前上下文的相关性，返回按相关性排序的 memory_id 列表。"""
        if not candidates:
            return []
        candidates_text = json.dumps(candidates, ensure_ascii=False, indent=2)
        user_content = f"Context:\n{context}\n\nCandidates:\n{candidates_text}"
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(model_type=ModelType.LLM.to_model_type())
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_RELEVANCE_JUDGE_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=user_content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            answer = cast(str, response.message.content).strip()
            raw = re.search(r"\[.*\]", answer, re.DOTALL)
            selected = json.loads(raw.group() if raw else answer)
            if isinstance(selected, list):
                return [str(mid) for mid in selected if mid]
        except Exception:
            logger.exception("judge_memory_relevance: failed, falling back to score order")
        return [c["id"] for c in candidates]

    @classmethod
    def generate_memory_tags(cls, content: str) -> str:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=TAG_STRUCTURED_OUTPUT_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.1,
            top_p=0.9,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
        answer = cast(str, response.message.content).strip()
        return answer

    @classmethod
    def judge_topic_merge(
        cls,
        topic_a: str,
        samples_a: list[str],
        topic_b: str,
        samples_b: list[str],
    ) -> dict:
        """判断两个话题是否应该合并。"""
        samples_a_text = "\n".join(f"- {s}" for s in samples_a[:3])
        samples_b_text = "\n".join(f"- {s}" for s in samples_b[:3])
        prompt = MEMORY_TOPIC_MERGE_JUDGE_PROMPT.format(
            topic_a=topic_a,
            samples_a=samples_a_text,
            topic_b=topic_b,
            samples_b=samples_b_text,
        )
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(model_type=ModelType.LLM.to_model_type())
        prompt_messages = [
            UserPromptMessage(role=PromptMessageRole.USER, content=prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            answer = cast(str, response.message.content).strip()
            return json.loads(answer)
        except Exception:
            logger.exception("judge_topic_merge: failed to parse response, return default")
            return {"should_merge": False, "reason": "parse_error", "merged_name": ""}

    @classmethod
    def evaluate_learning_params(cls, stats: dict) -> dict:
        """根据统计数据让 LLM 评估并返回优化后的学习参数。

        Args:
            stats: 包含 recent_cycles / cycle_trends / retrieval_quality /
                   signal_funnel / retrieval_text_summary / memory_quality /
                   type_ratio / topic_stats / current_params 的统计字典。
        Returns:
            解析成功时返回参数 dict（含 reasoning），失败时返回空 dict。
        """
        user_content = json.dumps(stats, ensure_ascii=False, indent=2)
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(model_type=ModelType.LLM.to_model_type())
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=LEARNING_PARAM_OPTIMIZE_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=user_content),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.1,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            answer = cast(str, response.message.content).strip()
            raw = re.search(r"\{.*\}", answer, re.DOTALL)
            return json.loads(raw.group() if raw else answer)
        except Exception:
            logger.exception("evaluate_learning_params: failed to parse LLM response")
            return {}

    @classmethod
    def distill_semantic_insight(
        cls,
        topic: str,
        episodic_memories: list[str],
    ) -> str:
        """从情景记忆群提炼语义洞见。"""
        memories_text = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(episodic_memories))
        prompt = MEMORY_INSIGHT_DISTILL_PROMPT.format(
            topic=topic,
            episodic_memories=memories_text,
        )
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(model_type=ModelType.LLM.to_model_type())
        prompt_messages = [
            UserPromptMessage(role=PromptMessageRole.USER, content=prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.3,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            return cast(str, response.message.content).strip()
        except Exception:
            logger.exception("distill_semantic_insight: LLM failed, return empty string")
            return ""

    @classmethod
    def choice_tool(cls, query: str, tool_schemas: list[dict]) -> list[str]:
        """根据用户请求推理工具相关性，返回按相关度排序的工具名称列表。

        Args:
            query: 用户原始请求。
            tool_schemas: ToolEntity.get_schema() 列表，包含 name/description/provider/type。
        Returns:
            相关工具名称列表（按相关性降序），无匹配时返回空列表。
        """
        if not tool_schemas:
            return []
        model_manager = ModelManager()
        model_instance = model_manager.get_tool_choice_model()
        tools_json = json.dumps(tool_schemas, ensure_ascii=False, indent=2)
        prompt = TOOL_SELECTION_PROMPT.format(user_request=query, tools=tools_json)
        prompt_messages = [
            UserPromptMessage(role=PromptMessageRole.USER, content=prompt),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response: ChatCompletionResponse = model_instance.invoke_llm_sync(prompt_messages=request)
            answer = cast(str, response.message.content).strip()
            raw = re.search(r"\[.*\]", answer, re.DOTALL)
            result = json.loads(raw.group() if raw else answer)
            if isinstance(result, list):
                return [str(name) for name in result if name]
        except Exception:
            logger.exception("choice_tool: failed to parse tool selection response")
        return []
