from typing import Optional

from pydantic import ConfigDict

from ..entities.embedding_type import EmbeddingInputType
from ..entities.model_entities import ModelType
from ..entities.text_embedding_entities import TextEmbeddingResult, EmbeddingRequest
from ..providers.base import AiModel


class TextEmbeddingModel(AiModel):
    """
    Model class for text embedding model.
    """
    model_type: ModelType = ModelType.EMBEDDING

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    def invoke(
        self,
        texts: EmbeddingRequest,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        """
        Invoke text embedding model

        :param texts: texts to embed
        :param input_type: input type
        :return: embeddings result
        """
        try:
            from ..transformation import get_llm_transformation
            transformation = get_llm_transformation(
                self.credentials.get("sdk_type", "openai_like"))

            credentials = transformation.setup_validate_credentials(self.credentials)
            if not texts.dimensions:
                texts.dimensions = self._get_max_tokens()
            result:TextEmbeddingResult= transformation.transform_embeddings(
                texts=texts,
                credentials=credentials,
            )
            return result
        except Exception as e:
            raise e

    def _get_max_tokens(self) -> Optional[int]:
        """
        Get max tokens for the model

        :return: max tokens
        """
        return self.model_params.get("MAX_EMBEDDING_TOKENS",1024)