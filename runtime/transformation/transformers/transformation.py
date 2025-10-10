import logging
import os
from typing import Union, Generator

from runtime.entities import ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest, CompletionResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse, RerankResult, RerankUsage
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.mcp.types import Request
from runtime.transformation import OpenAILikeTransformation
from runtime.transformation.transformers.transformers_manager import (
    TransformersManager,
    ReRankTransformersLoader,
    EmbeddingTransformersLoader,
)

logger = logging.getLogger("transformers")


class TransformersTransformation(OpenAILikeTransformation):
    _manager_instance = None
    _initialized_models = set()

    @classmethod
    def setup_environment(cls, credentials, params=None):
        _credentials = credentials["credentials"]
        return {
            "models_path": _credentials.get("models_path", ""),
            "sdk_type": credentials.get("sdk_type", "transformers"),
        }

    @classmethod
    def _get_manager(cls) -> TransformersManager:
        """Get or create TransformersManager instance"""
        if cls._manager_instance is None:
            cls._manager_instance = TransformersManager()
            cls._manager_instance.start_broker()
        return cls._manager_instance

    @classmethod
    def _ensure_model_loaded(cls, model_name: str, model_path: str, device: str = "cpu", model_type: str = "rerank"):
        """Ensure model is loaded and worker is started"""
        if model_name in cls._initialized_models:
            return

        try:
            manager = cls._get_manager()

            # Create appropriate loader based on model type
            if model_type == "rerank":
                loader = ReRankTransformersLoader(model=model_name, model_path=model_path, device=device)
            elif model_type == "embedding":
                loader = EmbeddingTransformersLoader(model=model_name, model_path=model_path, device=device)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")

            manager.start_worker(loader)
            cls._initialized_models.add(model_name)
            logger.info(f"Model {model_name} loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise

    @classmethod
    def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        """Transform rerank request using transformers manager"""
        try:
            # Extract model information from credentials or query
            models_path = credentials.get("models_path", "")
            model_name = query.model
            model_path = None
            if os.path.exists(models_path) and not os.path.isabs(model_name):
                model_path = os.path.join(models_path, model_name)

            device = "cpu"

            # Ensure model is loaded
            cls._ensure_model_loaded(model_name, model_path, device, "rerank")

            # Prepare task data
            task_data = {
                "query": [query.query] * len(query.documents),
                "documents": [doc for doc in query.documents],
                "top_n": query.top_n or len(query.documents),
            }

            # Send task to manager
            manager = cls._get_manager()
            response = manager.send_task(model_name, task_data)

            # if not response:
            #     response=manager.send_task(model_name, task_data)

            if not response.success:
                raise RuntimeError(f"Rerank failed: {response.data.get('error', 'Unknown error')}")

            # Convert to RerankResponse format
            reranked_docs = response.data["reranked_documents"]
            scores = response.data["scores"]

            # Create response objects
            from runtime.entities.rerank_entities import RerankDocument

            results = []
            for i, (doc_text, score) in enumerate(zip(reranked_docs, scores)):
                # Find original document index
                original_index = next(idx for idx, doc in enumerate(query.documents) if doc == doc_text)
                results.append(
                    RerankResult(index=original_index, document=RerankDocument(text=doc_text), relevance_score=score)
                )

            # Optionally stop worker to free resources
            manager.stop_worker(model_name)
            cls._initialized_models.remove(model_name)

            return RerankResponse(
                id="rerank-" + os.urandom(8).hex(),
                model=model_name,
                results=results,
                usage=RerankUsage(total_tokens=sum(len(doc.split()) for doc in query.documents)),
            )

        except Exception as e:
            logger.error(f"Error in rerank transformation: {e}")
            # Fallback to parent implementation
            raise e

    @classmethod
    def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        """Transform embeddings request using transformers manager"""
        try:
            # Extract model information
            models_path = credentials.get("models_path", "")
            model_name = texts.model
            model_path = None
            if os.path.exists(models_path) and not os.path.isabs(model_name):
                model_path = os.path.join(models_path, model_name)

            device = "cpu"

            # Ensure model is loaded
            cls._ensure_model_loaded(model_name, model_path, device, "embedding")

            # Prepare task data
            task_data = {
                "texts": texts.input if isinstance(texts.input, list) else [texts.input],
                "encoding_format": texts.encoding_format,
                "dimension": texts.dimensions,
            }

            # Send task to manager
            manager = cls._get_manager()
            response = manager.send_task(model_name, task_data)

            # if not response:
            #     response=manager.send_task(model_name, task_data)

            if not response.success:
                raise RuntimeError(f"Embedding failed: {response.data.get('error', 'Unknown error')}")

            # Convert to TextEmbeddingResult format
            embeddings = response.data["embeddings"]
            encoding_format = response.data.get("encoding_format", "float")

            from runtime.entities.text_embedding_entities import EmbeddingsResponse

            data = []
            for i, embedding in enumerate(embeddings):
                data.append(
                    EmbeddingsResponse(
                        index=i, embedding=embedding, object="embedding", encoding_format=encoding_format
                    )
                )

            return TextEmbeddingResult(
                object="list",
                data=data,
                model=model_name,
            )

        except Exception as e:
            logger.error(f"Error in embeddings transformation: {e}")
            # Fallback to parent implementation
            raise e

    @classmethod
    def transform_message(
            cls,
            model_params: dict,
            prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
            credentials: dict,
            stream: bool = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
        """Transform chat completion request using transformers manager"""
        try:
            # Extract model information
            model_name = credentials.get("model_name") or model_params.get("model")
            model_path = credentials.get("model_path", model_name)
            device = credentials.get("device", "cpu")

            # Ensure model is loaded
            cls._ensure_model_loaded(model_name, model_path, device, "chat")

            # Prepare task data
            if isinstance(prompt_messages, ChatCompletionRequest):
                task_data = {
                    "messages": [msg.model_dump() for msg in prompt_messages.messages],
                    "max_tokens": prompt_messages.max_tokens,
                    "temperature": prompt_messages.temperature,
                    "stream": stream or False,
                }
            else:
                task_data = {
                    "prompt": prompt_messages.prompt,
                    "max_tokens": prompt_messages.max_tokens,
                    "temperature": prompt_messages.temperature,
                    "stream": stream or False,
                }

            # Send task to manager
            manager = cls._get_manager()
            response = manager.send_task(model_name, task_data)

            if not response.success:
                raise RuntimeError(f"Chat completion failed: {response.data.get('error', 'Unknown error')}")

            # Return response data
            return response.data["response"]

        except Exception as e:
            logger.error(f"Error in message transformation: {e}")
            # Fallback to parent implementation
            raise e

    @classmethod
    def cleanup(cls):
        """Cleanup resources"""
        if cls._manager_instance:
            cls._manager_instance.stop_all()
            cls._manager_instance = None
            cls._initialized_models.clear()
