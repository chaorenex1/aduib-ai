import logging
from typing import Sequence, Optional, Literal, Generator, overload, Union, cast, Callable, Any, IO, Iterable

from .callbacks.base_callback import Callback
from .entities import PromptMessage, PromptMessageTool, LLMResult
from .entities.embedding_type import EmbeddingInputType
from .entities.message_entities import PromptMessageFunction
from .entities.model_entities import ModelType
from .entities.provider_entities import ProviderEntity
from .entities.rerank_entities import RerankResult
from .entities.text_embedding_entities import TextEmbeddingResult
from .provider_manager import ProviderManager
from .providers.audio2text_model import Audio2TextModel
from .providers.base import AiModel
from .providers.large_language_model import LlmModel
from .providers.model_provider_factory import ModelProviderFactory
from .providers.rerank_model import RerankModel
from .providers.text_embedding_model import TextEmbeddingModel
from .providers.tts_model import TTSModel

logger = logging.getLogger(__name__)

class ModelInstance:

    """
    Model Instance
    """

    def __init__(self,provider:ProviderEntity, model_instance: AiModel, model: str):
        self.provider = provider
        self.model_instance = model_instance
        self.credentials= provider.provider_credential.credentials
        self.credentials["sdkType"] = provider.provider_credential.sdk_type
        self.model = model

    @overload
    def invoke_llm(
            self,
            prompt_messages: Sequence[PromptMessage],
            model_parameters: Optional[dict] = None,
            tools: Sequence[PromptMessageFunction] | None = None,
            stop: Optional[list[str]] = None,
            stream: Literal[True] = True,
            callbacks: Optional[list[Callback]] = None,
    ) -> Generator: ...

    @overload
    def invoke_llm(
            self,
            prompt_messages: list[PromptMessage],
            model_parameters: Optional[dict] = None,
            tools: Sequence[PromptMessageFunction] | None = None,
            stop: Optional[list[str]] = None,
            stream: Literal[False] = False,
            callbacks: Optional[list[Callback]] = None,
    ) -> LLMResult: ...

    @overload
    def invoke_llm(
            self,
            prompt_messages: list[PromptMessage],
            model_parameters: Optional[dict] = None,
            tools: Sequence[PromptMessageFunction] | None = None,
            stop: Optional[list[str]] = None,
            stream: bool = True,
            callbacks: Optional[list[Callback]] = None,
    ) -> Union[LLMResult, Generator]: ...

    def invoke_llm(
            self,
            prompt_messages: Sequence[PromptMessage],
            model_parameters: Optional[dict] = None,
            tools: Sequence[PromptMessageFunction] | None = None,
            stop: Optional[Sequence[str]] = None,
            stream: bool = True,
            callbacks: Optional[list[Callback]] = None,
    ) -> Union[LLMResult, Generator]:
        """
        Invoke large language model

        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result
        """
        if not isinstance(self.model_instance, LlmModel):
            raise Exception("Model type instance is not LargeLanguageModel")

        self.model_type_instance = cast(LlmModel, self.model_instance)
        return cast(
            Union[LLMResult, Generator],
            self._round_robin_invoke(
                function=self.model_type_instance.invoke,
                model=self.model,
                credentials=self.credentials,
                prompt_messages=prompt_messages,
                model_parameters=model_parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
            ),
        )


    def invoke_text_embedding(
        self, texts: list[str], input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT
    ) -> TextEmbeddingResult:
        """
        Invoke large language model

        :param texts: texts to embed
        :param user: unique user id
        :param input_type: input type
        :return: embeddings result
        """
        if not isinstance(self.model_instance, TextEmbeddingModel):
            raise Exception("Model type instance is not TextEmbeddingModel")

        self.model_instance = cast(TextEmbeddingModel, self.model_type_instance)
        return cast(
            TextEmbeddingResult,
            self._round_robin_invoke(
                function=self.model_instance.invoke,
                model=self.model,
                credentials=self.credentials,
                texts=texts,
                input_type=input_type,
            ),
        )

    def invoke_rerank(
        self,
        query: str,
        docs: list[str],
        score_threshold: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> RerankResult:
        """
        Invoke rerank model

        :param query: search query
        :param docs: docs for reranking
        :param score_threshold: score threshold
        :param top_n: top n
        :param user: unique user id
        :return: rerank result
        """
        if not isinstance(self.model_type_instance, RerankModel):
            raise Exception("Model type instance is not RerankModel")

        self.model_instance = cast(RerankModel, self.model_type_instance)
        return cast(
            RerankResult,
            self._round_robin_invoke(
                function=self.model_type_instance.invoke,
                model=self.model,
                credentials=self.credentials,
                query=query,
                docs=docs,
                score_threshold=score_threshold,
                top_n=top_n,
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
        if not isinstance(self.model_type_instance, Audio2TextModel):
            raise Exception("Model type instance is not Speech2TextModel")

        self.model_instance = cast(Audio2TextModel, self.model_type_instance)
        return cast(
            str,
            self._round_robin_invoke(
                function=self.model_instance.invoke,
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
        if not isinstance(self.model_type_instance, TTSModel):
            raise Exception("Model type instance is not TTSModel")

        self.model_instance = cast(TTSModel, self.model_type_instance)
        return cast(
            Iterable[bytes],
            self._round_robin_invoke(
                function=self.model_instance.invoke,
                model=self.model,
                credentials=self.credentials,
                content_text=content_text,
                voice=voice,
            ),
        )

    def _round_robin_invoke(self, function: Callable[..., Any], *args, **kwargs) -> Any:
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
        self.provider_factory = ModelProviderFactory()

    def get_model_instance(self, provider: str, model_type: ModelType, model: str) -> ModelInstance:
        """
        Get model instance
        :param provider: provider name
        :param model_type: model type
        :param model: model name
        :return:
        """
        model_instance = self.provider_factory.get_model_type_instance(provider, model_type)
        provider_entity = self.provider.get_provider_entity(provider)
        return ModelInstance(provider_entity,model_instance, model)
