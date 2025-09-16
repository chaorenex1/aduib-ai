from typing import IO, Optional

from pydantic import ConfigDict

from ..entities.model_entities import ModelType
from ..model_execution.base import AiModel


class Audio2TextModel(AiModel):
    model_type: ModelType = ModelType.ASR

    model_config = ConfigDict(protected_namespaces=())

    def invoke(self, model: str, credentials: dict, file: IO[bytes], user: Optional[str] = None) -> str:
        """
        Invoke speech to text model

        :param model: model name
        :param credentials: model credentials
        :param file: audio file
        :param user: unique user id
        :return: text for given audio file
        """
        try:
            # plugin_model_manager = PluginModelClient()
            # return plugin_model_manager.invoke_speech_to_text(
            #     tenant_id=self.tenant_id,
            #     user_id=user or "unknown",
            #     plugin_id=self.plugin_id,
            #     provider=self.provider_name,
            #     model=model,
            #     credentials=credentials,
            #     file=file,
            # )
            pass
        except Exception as e:
            raise self._transform_invoke_error(e)
