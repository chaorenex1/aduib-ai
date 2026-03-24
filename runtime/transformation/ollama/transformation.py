import json
import logging
import uuid

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities.llm_entities import ChatCompletionRequest, LLMRequest, LLMResponse
from runtime.entities.message_entities import PromptMessage, PromptMessageRole
from runtime.entities.rerank_entities import (
    RerankDocument,
    RerankRequest,
    RerankResponse,
    RerankResult,
    RerankUsage,
)
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.transformation.base import LLMTransformation

logger = logging.getLogger(__name__)


class OllamaTransformation(LLMTransformation):
    """
    Translates from OpenAI-like API to Ollama API.

    Ollama API specifics:
    - API Base: http://localhost:11434
    - Chat endpoint: /api/chat (not /v1/chat/completions)
    - Embeddings endpoint: /api/embeddings
    - API Key: Optional (Ollama doesn't require it)
    """

    provider_type = "ollama"
    DEFAULT_API_BASE = "http://localhost:11434"

    @classmethod
    def setup_environment(cls, credentials, params=None):
        _credentials = credentials.get("credentials", {})
        api_base = _credentials.get("api_base", cls.DEFAULT_API_BASE)
        api_key = _credentials.get("api_key")

        headers = {"Content-Type": "application/json;charset=utf-8"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        user_agent = "AduibLLM-Ollama-Client/1.0"
        if params:
            user_agent = params.get("user_agent") or user_agent
        if user_agent:
            headers["User-Agent"] = user_agent

        return {
            "api_key": api_key,
            "api_base": api_base,
            "headers": headers,
            "sdk_type": credentials.get("sdk_type"),
        }

    @classmethod
    async def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: LLMRequest,
        credentials: dict,
        stream: bool = None,
    ) -> LLMResponse:
        llm_http_handler = LLMHttpHandler("/api/chat", credentials, stream)
        return await llm_http_handler.completion_request(prompt_messages)

    @classmethod
    async def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        llm_http_handler = LLMHttpHandler("/api/embeddings", credentials, False)
        return await llm_http_handler.embedding_request(texts)

    @classmethod
    async def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        """
        Transform rerank request for Ollama API using LLM-based document scoring.

        Since Ollama doesn't have a dedicated rerank endpoint, this method uses
        the /api/chat endpoint to evaluate document relevance with an LLM.

        Args:
            query: Rerank request containing query, documents, and top_n
            credentials: API credentials

        Returns:
            RerankResponse with relevance scores for each document
        """
        # Type validation and conversion for query
        if isinstance(query.query, list):
            query_text = query.query[0] if query.query else ""
        else:
            query_text = query.query or ""  # Treat None/empty as empty string

        # Type validation and conversion for documents
        if isinstance(query.documents, str):
            documents: list[str] = [query.documents]
        else:
            documents = query.documents

        # Early return for empty documents
        if not documents:
            return RerankResponse(
                id=str(uuid.uuid4()),
                model=query.model or "unknown",
                usage=RerankUsage(total_tokens=0),
                results=[],
            )

        # Build rerank prompt
        prompt = cls._build_rerank_prompt(query_text, documents)

        # Create chat request for Ollama using proper request type
        chat_request = ChatCompletionRequest(
            model=query.model,
            messages=[
                PromptMessage(role=PromptMessageRole.USER, content=prompt)
            ],
            temperature=0.1,  # Low temperature for consistent scoring
            stream=False,
        )

        # Use chat endpoint for reranking
        llm_http_handler = LLMHttpHandler("/api/chat", credentials, False)
        response = await llm_http_handler.completion_request(chat_request)

        # Parse LLM response and build RerankResponse
        return cls._parse_rerank_response(response, query.model, query.top_n, documents)

    @classmethod
    def _build_rerank_prompt(cls, query: str, documents: list[str]) -> str:
        """Build prompt for LLM-based document relevance evaluation."""
        documents_text = "\n".join(
            f"[{i}] {doc}" for i, doc in enumerate(documents)
        )

        return f"""You are a document relevance evaluator. Given a query and a list of documents,
evaluate how relevant each document is to the query. Return a JSON array with relevance scores.

Query: {query}

Documents:
{documents_text}

Return format:
[
  {{"index": 0, "score": 0.95, "reason": "brief explanation"}},
  {{"index": 1, "score": 0.72, "reason": "brief explanation"}}
]

Scores must be between 0.0 and 1.0. Only return the JSON array."""

    @classmethod
    def _parse_rerank_response(
        cls, response, model: str | None, top_n: int, documents: list[str]
    ) -> RerankResponse:
        """Parse LLM response into RerankResponse."""
        # Extract content from LLM response
        content = response.message.content if hasattr(response, "message") else str(response)

        # Parse JSON from response with error handling
        try:
            parsed_scores = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse rerank response: {e}")
            raise ValueError("Invalid JSON response from LLM") from e

        # Build RerankResults, sorted by score descending
        sorted_scores = sorted(parsed_scores, key=lambda x: x.get("score", 0), reverse=True)

        # Handle top_n: if None or negative, return all results
        if top_n is None or top_n < 0:
            top_n = len(sorted_scores)

        # Apply top_n limit if specified
        if top_n > 0:
            sorted_scores = sorted_scores[:top_n]

        results = []
        for score_item in sorted_scores:
            idx = score_item.get("index")
            # Skip invalid indices instead of returning empty document
            if idx >= len(documents):
                logger.warning(f"Rerank index {idx} out of bounds, skipping")
                continue
            doc_text = documents[idx]
            results.append(
                RerankResult(
                    index=idx,
                    document=RerankDocument(text=doc_text),
                    relevance_score=score_item.get("score", 0.0),
                )
            )

        # Extract usage information
        usage = response.usage if hasattr(response, 'usage') else None
        total_tokens = usage.total_tokens if usage else 0

        return RerankResponse(
            id=str(uuid.uuid4()),
            model=model or "unknown",
            usage=RerankUsage(total_tokens=total_tokens),
            results=results,
        )
