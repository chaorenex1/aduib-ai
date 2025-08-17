from .audio2text_model import Audio2TextModel
from .base import AiModel
from .large_language_model import LlMModel
from .rerank_model import RerankModel
from .text_embedding_model import TextEmbeddingModel
from .tts_model import TTSModel
from ..entities.model_entities import ModelType
from ..entities.provider_entities import ProviderEntity


class ModelProviderFactory:

    def get_model_type_instance(self, provider: ProviderEntity, model_type: ModelType) -> None | AiModel:
        """
        Get model type instance by provider name and model type
        :param provider: provider name
        :return: model type instance
        """
        init_params = {
            "provider_name": provider.provider,
            "model_type": model_type.to_model_type(),
            "model_provider": provider
        }

        if model_type == ModelType.LLM:
            return LlMModel(**init_params)  # type: ignore
        elif model_type == ModelType.EMBEDDING:
            return TextEmbeddingModel(**init_params)  # type: ignore
        elif model_type == ModelType.RANKER:
            return RerankModel(**init_params)  # type: ignore
        elif model_type == ModelType.ASR:
            return Audio2TextModel(**init_params)  # type: ignore
        elif model_type == ModelType.MODERATION:
            return ModerationModel(**init_params)  # type: ignore
        elif model_type == ModelType.TTS:
            return TTSModel(**init_params)  # type: ignore

