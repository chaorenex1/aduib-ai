
from .base import AiModel
from ..entities.model_entities import ModelType


class ModelProviderFactory:

    def get_model_type_instance(self, provider_name: str, model_type: ModelType) -> AiModel:
        """
        Get model type instance by provider name and model type
        :param provider: provider name
        :return: model type instance
        """
        init_params = {
            "provider_name": provider_name,
        }

        if model_type == ModelType.LLM:
            return LargeLanguageModel(**init_params)  # type: ignore
        elif model_type == ModelType.TEXT_EMBEDDING:
            return TextEmbeddingModel(**init_params)  # type: ignore
        elif model_type == ModelType.RERANK:
            return RerankModel(**init_params)  # type: ignore
        elif model_type == ModelType.SPEECH2TEXT:
            return Speech2TextModel(**init_params)  # type: ignore
        elif model_type == ModelType.MODERATION:
            return ModerationModel(**init_params)  # type: ignore
        elif model_type == ModelType.TTS:
            return TTSModel(**init_params)  # type: ignore

