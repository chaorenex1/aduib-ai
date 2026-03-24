import logging
from collections.abc import Iterable
from typing import Optional

from pydantic import ConfigDict

from runtime.entities.model_entities import ModelType
from runtime.model_execution.base import AiModel

logger = logging.getLogger(__name__)


class TTSModel(AiModel):
    """
    Model class for TTS model.
    """

    model_type: ModelType = ModelType.TTS

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    def invoke(
        self,
        model: str,
        credentials: dict,
        content_text: str,
        voice: str,
        user: Optional[str] = None,
    ) -> Iterable[bytes]:
        """
        Invoke tts model

        :param model: model name
        :param credentials: model credentials
        :param content_text: text content to be translated
        :param voice: model timbre
        :param user: unique user id
        :return: translated audio file
        """
        try:
            import asyncio

            from runtime.entities.provider_entities import ProviderSDKType
            from runtime.entities.tts_entities import TTSRequest
            from runtime.transformation.types import get_llm_transformation

            tts_request = TTSRequest(
                model=model,
                input=content_text,
                voice=voice,
                user=user,
            )

            # Get the transformation class based on sdk_type
            sdk_type_str = credentials.get("sdk_type", "openai_like")
            sdk_type = ProviderSDKType.value_of(sdk_type_str)
            transformation = get_llm_transformation(sdk_type)

            credentials = transformation.setup_environment(credentials, self.model_params)
            result = asyncio.run(transformation.transform_tts(tts_request, credentials))

            return result.audio_data
        except Exception as e:
            raise type(e)(f"Error invoking TTS model: {e}") from e

    def get_tts_model_voices(self, model: str, credentials: dict, language: Optional[str] = None) -> list[dict]:
        """
        Retrieves the list of voices supported by a given text-to-speech (TTS) model.

        :param model: The name of the TTS model.
        :param credentials: The credentials required to access the TTS model.
        :param language: The language for which the voices are requested.
        :return: A list of voices supported by the TTS model.
        """
        try:
            import asyncio

            from runtime.entities.provider_entities import ProviderSDKType
            from runtime.transformation.types import get_llm_transformation

            # Get the transformation class based on sdk_type
            sdk_type_str = credentials.get("sdk_type", "openai_like")
            sdk_type = ProviderSDKType.value_of(sdk_type_str)
            transformation = get_llm_transformation(sdk_type)

            credentials = transformation.setup_environment(credentials, self.model_params)
            result = asyncio.run(transformation.transform_tts_voices(model, credentials, language))

            return result
        except Exception as e:
            raise type(e)(f"Error getting TTS model voices: {e}") from e
