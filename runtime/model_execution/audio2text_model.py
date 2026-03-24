import asyncio
from typing import IO, Optional

from pydantic import ConfigDict

from runtime.entities.provider_entities import ProviderSDKType
from runtime.entities.asr_entities import ASRRequest
from runtime.transformation.types import get_llm_transformation
from ..entities.model_entities import ModelType
from ..model_execution.base import AiModel

# Maximum ASR input audio size: 100MB
MAX_AUDIO_SIZE_BYTES = 100 * 1024 * 1024


class Audio2TextModel(AiModel):
    model_type: ModelType = ModelType.ASR

    model_config = ConfigDict(protected_namespaces=())

    def invoke(
        self,
        model: str,
        credentials: dict,
        file: IO[bytes],
        user: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: Optional[str] = "json",
        temperature: Optional[float] = 0.0,
    ) -> str:
        """
        Invoke speech to text model

        :param model: model name
        :param credentials: model credentials
        :param file: audio file
        :param user: unique user id
        :param language: language code (e.g., 'en', 'zh')
        :param prompt: optional prompt to guide the model
        :param response_format: response format (json, text, srt, verbose_json)
        :param temperature: sampling temperature (0.0 to 1.0)
        :return: text for given audio file
        """
        try:
            # Read file content
            file_content = file.read() if hasattr(file, "read") else file

            # Security check: validate audio data size to prevent memory exhaustion
            if len(file_content) > MAX_AUDIO_SIZE_BYTES:
                raise ValueError(
                    f"Audio file too large: {len(file_content)} bytes exceeds maximum "
                    f"allowed size of {MAX_AUDIO_SIZE_BYTES} bytes"
                )

            asr_request = ASRRequest(
                model=model,
                file=file_content,
                language=language,
                prompt=prompt,
                response_format=response_format,
                temperature=temperature,
                user=user,
            )

            # Get the transformation class based on sdk_type
            sdk_type_str = credentials.get("sdk_type", "openai_like")
            sdk_type = ProviderSDKType.value_of(sdk_type_str)
            transformation = get_llm_transformation(sdk_type)

            credentials = transformation.setup_environment(credentials, self.model_params)
            result = asyncio.run(transformation.transform_audio2text(asr_request, credentials))

            return result.text
        except Exception as e:
            raise type(e)(f"Error invoking ASR model: {e}") from e
