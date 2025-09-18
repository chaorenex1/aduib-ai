import json
import logging
import re
from typing import cast

from runtime.entities import UserPromptMessage, ChatCompletionResponse, SystemPromptMessage, PromptMessage
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.model_entities import ModelType
from runtime.generator.prompts import CONVERSATION_TITLE_PROMPT, GENERATOR_QA_PROMPT
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)


class LLMGenerator:
    @classmethod
    def generate_conversation_name(cls, query):
        cleaned_answer, query = cls._generate_conversation_name(query)
        if cleaned_answer is None:
            return ""
        try:
            result_dict = json.loads(cleaned_answer)
            answer = result_dict["Your Output"]
        except json.JSONDecodeError:
            logger.exception("Failed to generate name after answer, use query instead")
            answer = query
        name = answer.strip()

        if len(name) > 75:
            name = name[:75] + "..."

        return name

    @classmethod
    def _generate_conversation_name(cls, query):
        prompt = CONVERSATION_TITLE_PROMPT
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")
        prompt += query + "\n"
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM,
        )
        prompts = [UserPromptMessage(content=prompt)]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompts,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        cleaned_answer = re.sub(r"^.*(\{.*\}).*$", r"\1", answer, flags=re.DOTALL)
        return cleaned_answer, query

    @classmethod
    def generate_qa_document(cls, query:str, document_language: str):
        prompt = GENERATOR_QA_PROMPT.format(language=document_language)

        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM,
        )

        prompt_messages: list[PromptMessage] = [SystemPromptMessage(content=prompt), UserPromptMessage(content=query)]

        # Explicitly use the non-streaming overload
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
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
