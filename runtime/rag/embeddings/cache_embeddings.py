import base64
import hashlib
import logging
from typing import Any, Optional

import numpy as np
from sqlalchemy.exc import IntegrityError

from component.cache.redis_cache import redis_client
from configs import config
from models import get_db, KnowledgeEmbeddings
from runtime.entities.embedding_type import EmbeddingInputType
from runtime.entities.text_embedding_entities import EmbeddingRequest
from runtime.model_manager import ModelInstance
from runtime.rag.embeddings.embeddings import Embeddings

logger = logging.getLogger(__name__)


class CacheEmbeddings(Embeddings):
    def __init__(self, model_instance: ModelInstance):
        self._model_instance = model_instance

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs in batches of 10."""
        # use doc embedding cache or store if not exists
        with get_db() as session:
            text_embeddings: list[Any] = [None for _ in range(len(texts))]
            embedding_queue_indices = []
            for i, text in enumerate(texts):
                hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                embedding = (
                    session.query(KnowledgeEmbeddings)
                    .filter_by(hash=hash)
                    .one_or_none()
                )
                if embedding and embedding.vector:
                    text_embeddings[i] = embedding.vector
                else:
                    embedding_queue_indices.append(i)
            if embedding_queue_indices:
                embedding_queue_texts = [texts[i] for i in embedding_queue_indices]
                embedding_queue_embeddings = []
                for i in range(0, len(embedding_queue_texts), 10):
                    batch_texts = embedding_queue_texts[i : i + 10]
                    embedding_result = self._model_instance.invoke_text_embedding(
                        texts=EmbeddingRequest(input=batch_texts, model=self._model_instance.model),
                        input_type=EmbeddingInputType.DOCUMENT,
                    )

                for vector in embedding_result.data:
                    try:
                        normalized_embedding = (vector.embedding / np.linalg.norm(vector.embedding)).tolist()  # type: ignore
                        # stackoverflow best way: https://stackoverflow.com/questions/20319813/how-to-check-list-containing-nan
                        if np.isnan(normalized_embedding).any():
                            # for issue #11827  float values are not json compliant
                            logger.warning("Normalized embedding is nan: %s", normalized_embedding)
                            continue
                        embedding_queue_embeddings.append(normalized_embedding)
                    except IntegrityError:
                        session.rollback()
                    except Exception:
                        logger.exception("Failed transform embedding")
                for i, n_embedding in zip(embedding_queue_indices, embedding_queue_embeddings):
                    text_embeddings[i] = n_embedding
        return text_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed query text."""
        # use doc embedding cache or store if not exists
        hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        embedding_cache_key = f"{self._model_instance.provider}_{self._model_instance.model}_{hash}"
        embedding = redis_client.get(embedding_cache_key)
        if embedding:
            redis_client.expire(embedding_cache_key, 600)
            decoded_embedding = np.frombuffer(base64.b64decode(embedding), dtype="float")
            return [float(x) for x in decoded_embedding]
        try:
            embedding_result = self._model_instance.invoke_text_embedding(
                texts=EmbeddingRequest(input=[text], model=self._model_instance.model),
                input_type=EmbeddingInputType.QUERY,
            )

            embedding_results = embedding_result.data[0].embedding
            # FIXME: type ignore for numpy here
            embedding_results = (embedding_results / np.linalg.norm(embedding_results)).tolist()  # type: ignore
            if np.isnan(embedding_results).any():
                raise ValueError("Normalized embedding is nan please try again")
        except Exception as ex:
            if config.DEBUG:
                logger.exception("Failed to embed query text '%s...(%s chars)'", text[:10], len(text))
            raise ex

        try:
            # encode embedding to base64
            embedding_vector = np.array(embedding_results)
            vector_bytes = embedding_vector.tobytes()
            # Transform to Base64
            encoded_vector = base64.b64encode(vector_bytes)
            # Transform to string
            encoded_str = encoded_vector.decode("utf-8")
            redis_client.setex(embedding_cache_key, 600, encoded_str)
        except Exception as ex:
            if config.DEBUG:
                logger.exception(
                    "Failed to add embedding to redis for the text '%s...(%s chars)'", text[:10], len(text)
                )
            raise ex

        return embedding_results  # type: ignore
