import json
import logging
from typing import Optional, Generator, Union, cast, Callable, Any, IO, Iterable

from models import Provider, Model
from .callbacks.base_callback import Callback
from .entities import ChatCompletionResponse
from .entities.embedding_type import EmbeddingInputType
from .entities.llm_entities import ChatCompletionRequest, CompletionRequest, CompletionResponse
from .entities.model_entities import AIModelEntity, ModelType
from .entities.provider_entities import ProviderEntity
from .entities.rerank_entities import RerankRequest, RerankResponse
from .entities.text_embedding_entities import TextEmbeddingResult, EmbeddingRequest
from .model_execution.audio2text_model import Audio2TextModel
from .model_execution.base import AiModel
from .model_execution.large_language_model import LlMModel
from .model_execution.rerank_model import RerankModel
from .model_execution.text_embedding_model import TextEmbeddingModel
from .model_execution.tts_model import TTSModel
from .provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class ModelInstance:
    """
    Model Instance
    """

    def __init__(self, provider: ProviderEntity, model_instance: AiModel, model: str):
        self.provider = provider
        self.model_instance = model_instance
        self.credentials = provider.provider_credential.credentials
        self.credentials["sdk_type"] = provider.provider_credential.sdk_type
        self.model = model

    def invoke_llm(
        self,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        callbacks: Optional[list[Callback]] = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
        """
        Invoke large language model

        :param prompt_messages: prompt messages
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result
        """
        if not isinstance(self.model_instance, LlMModel):
            raise Exception("Model type instance is not LargeLanguageModel")

        self.model_type_instance = cast(LlMModel, self.model_instance)
        return cast(
            Union[CompletionResponse, Generator[CompletionResponse, None, None]],
            self._invoke(
                function=self.model_type_instance.invoke,
                req=prompt_messages,
                callbacks=callbacks,
            ),
        )

    def invoke_text_embedding(
        self, texts: EmbeddingRequest, input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT
    ) -> TextEmbeddingResult:
        """
        Invoke large language model

        :param texts: texts to embed
        :param input_type: input type
        :return: embeddings result
        """
        if not isinstance(self.model_instance, TextEmbeddingModel):
            raise Exception("Model type instance is not TextEmbeddingModel")

        self.model_type_instance = cast(TextEmbeddingModel, self.model_instance)
        return cast(
            TextEmbeddingResult,
            self._invoke(
                function=self.model_type_instance.invoke,
                texts=texts,
                input_type=input_type,
            ),
        )

    def get_text_embedding_num_tokens(self, texts: list[str]) -> int:
        """
        Get text embedding num tokens

        :param texts: text to embed
        :return: num tokens
        """
        if not isinstance(self.model_instance, TextEmbeddingModel):
            raise Exception("Model type instance is not TextEmbeddingModel")

        self.model_type_instance = cast(TextEmbeddingModel, self.model_instance)
        return cast(
            int,
            self._invoke(
                function=self.model_type_instance.get_num_tokens,
                texts=texts,
            ),
        )

    def invoke_rerank(self, query: RerankRequest) -> RerankResponse:
        """
        Invoke rerank model

        :param query: search query
        :param docs: docs for reranking
        :param score_threshold: score threshold
        :param top_n: top n
        :param user: unique user id
        :return: rerank result
        """
        if not isinstance(self.model_instance, RerankModel):
            raise Exception("Model type instance is not RerankModel")

        self.model_type_instance = cast(RerankModel, self.model_instance)
        return cast(
            RerankResponse,
            self._invoke(
                function=self.model_type_instance.invoke,
                query=query,
            ),
        )

    def invoke_moderation(self, text: str) -> bool:
        """
        Invoke moderation model

        :param text: text to moderate
        :param user: unique user id
        :return: false if text is safe, true otherwise
        """
        return False

    def invoke_speech2text(self, file: IO[bytes]) -> str:
        """
        Invoke large language model

        :param file: audio file
        :param user: unique user id
        :return: text for given audio file
        """
        if not isinstance(self.model_instance, Audio2TextModel):
            raise Exception("Model type instance is not Speech2TextModel")

        self.model_type_instance = cast(Audio2TextModel, self.model_instance)
        return cast(
            str,
            self._invoke(
                function=self.model_type_instance.invoke,
                model=self.model,
                credentials=self.credentials,
                file=file,
            ),
        )

    def invoke_tts(self, content_text: str, voice: str) -> Iterable[bytes]:
        """
        Invoke large language tts model

        :param content_text: text content to be translated
        :param tenant_id: user tenant id
        :param voice: model timbre
        :param user: unique user id
        :return: text for given audio file
        """
        if not isinstance(self.model_instance, TTSModel):
            raise Exception("Model type instance is not TTSModel")

        self.model_type_instance = cast(TTSModel, self.model_instance)
        return cast(
            Iterable[bytes],
            self._invoke(
                function=self.model_type_instance.invoke,
                model=self.model,
                credentials=self.credentials,
                content_text=content_text,
                voice=voice,
            ),
        )

    def _invoke(self, function: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Round-robin invoke
        :param function: function to invoke
        :param args: function args
        :param kwargs: function kwargs
        :return:
        """
        try:
            return function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error invoking function: {e}")
            raise e


class ModelManager:
    """
    Model Manager
    """

    def __init__(self):
        self.provider = ProviderManager()

    def get_model_instance(self, model_name: str, provider_name: str = None) -> Optional[ModelInstance]:
        from service import ModelService, ProviderService

        if provider_name:
            model: Model = ModelService.get_model_by_provider(model_name, provider_name)
        else:
            model: Model = ModelService.get_model(model_name)
        provider: Provider = ProviderService.get_provider(model.provider_name)
        model_list: list[AIModelEntity] = ModelService.get_ai_models(provider.name)
        provider_entity = self.provider.get_provider_entity(provider, model_list)
        model_instance = self.provider.provider_factory.get_model_type_instance(
            provider_entity, json.loads(model.model_params), ModelType.value_of(model.type)
        )
        return ModelInstance(provider_entity, model_instance, model.name)

    def get_default_model_instance(self, model_type: str):
        from service import ModelService, ProviderService

        model: Model = ModelService.get_default_model(model_type)
        if not model:
            return None
        provider: Provider = ProviderService.get_provider(model.provider_name)
        model_list: list[AIModelEntity] = ModelService.get_ai_models(provider.name)
        provider_entity = self.provider.get_provider_entity(provider, model_list)
        model_instance = self.provider.provider_factory.get_model_type_instance(
            provider_entity, json.loads(model.model_params), ModelType.value_of(model.type)
        )
        return ModelInstance(provider_entity, model_instance, model.name)
