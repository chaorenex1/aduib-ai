import json
import logging
import re
from typing import cast, Any

from runtime.entities import (
    UserPromptMessage,
    ChatCompletionResponse,
    SystemPromptMessage,
    PromptMessage,
    PromptMessageRole,
)
from runtime.entities.document_entities import Document
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.model_entities import ModelType
from runtime.generator.prompts import (
    CONVERSATION_TITLE_PROMPT,
    GENERATOR_QA_PROMPT,
    SYSTEM_STRUCTURED_OUTPUT_GENERATE,
    SUMMARY_PROMPT,
    TRIPLES_PROMPT, ANSWER_INSTRUCTION_FROM_KNOWLEDGE, TOOL_CHiOCE_PROMPT,BLOG_TRANSFORM_PROMPT
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
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
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
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

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
            response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)

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
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer.strip()

    @classmethod
    def generate_retrieval_content(cls, query: str, results: list[Document], rag_type: str) -> str:
        question=query
        contexts:list[dict[str,Any]] = []
        if rag_type == "paragraph":
            for result in results:
                contexts.append({"doc_id": result.metadata.get("doc_id"), "content": result.content})
            context = json.dumps(contexts, ensure_ascii=False, indent=2)
        else:
            for result in results:
                contexts.append({"doc_id": result.metadata.get("doc_id"), "question": result.content, "answer": result.metadata.get("answer")})
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
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer

    @classmethod
    def choice_tool_invoke(cls, tools:list[Tool], query:str)-> dict:
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            model_type=ModelType.LLM.to_model_type(),
        )
        _tools="".join("<tool>\n<name>"+tool.entity.name+"</name>\n<description>"+tool.entity.description+"</description>\n<arguments>"+json.dumps(tool.entity.parameters)+"</arguments>\n</tool>\n" for tool in tools)
        TOOL_CHiOCE_PROMPT.format(_tools=_tools)
        prompt_messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=TOOL_CHiOCE_PROMPT),
            UserPromptMessage(role=PromptMessageRole.USER, content=query),
        ]

        # Explicitly use the non-streaming overload
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=prompt_messages,
            temperature=0.01,
            stream=False,
        )
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        # search <tool_use>
        #   <name>...</name>
        #   <arguments>...</arguments>
        # </tool_use>
        match = re.search(r"<tool_use>\s*<name>(.*?)</name>\s*<arguments>(.*?)</arguments>\s*</tool_use>", answer, re.DOTALL)
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
    def generate_content(cls, prompt: str,temperature:float=0.7) -> str:
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
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer.strip()


    @classmethod
    def generate_doc_research(cls, raw_content:str) -> str:
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
        response: ChatCompletionResponse = model_instance.invoke_llm(prompt_messages=request)
        answer = cast(str, response.message.content)
        return answer