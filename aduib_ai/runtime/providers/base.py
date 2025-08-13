from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from ..entities.model_entities import AIModelEntity
from ..entities.provider_entities import ProviderEntity


class AiModel(BaseModel):
    model_type: str=Field(description="Model type")
    provider_name: str=Field(description="Provider name")
    model_provider: ProviderEntity=Field(description="Model provider")

    # model_config: ConfigDict =Field(description="Model config", protected_namespaces=())


    def get_model_schema(self, model: str, credentials: Optional[dict] = None) -> Optional[AIModelEntity]:
        """
        Get model schema by model name and credentials

        :param model: model name
        :param credentials: model credentials
        :return: model schema
        """
        schema: Optional[AIModelEntity] = None
        # plugin_model_manager = PluginModelClient()
        # cache_key = f"{self.tenant_id}:{self.plugin_id}:{self.provider_name}:{self.model_type.value}:{model}"
        # # sort credentials
        # sorted_credentials = sorted(credentials.items()) if credentials else []
        # cache_key += ":".join([hashlib.md5(f"{k}:{v}".encode()).hexdigest() for k, v in sorted_credentials])
        #
        # try:
        #     contexts.plugin_model_schemas.get()
        # except LookupError:
        #     contexts.plugin_model_schemas.set({})
        #     contexts.plugin_model_schema_lock.set(Lock())
        #
        # with contexts.plugin_model_schema_lock.get():
        #     if cache_key in contexts.plugin_model_schemas.get():
        #         return contexts.plugin_model_schemas.get()[cache_key]
        #
        #     schema = plugin_model_manager.get_model_schema(
        #         tenant_id=self.tenant_id,
        #         user_id="unknown",
        #         plugin_id=self.plugin_id,
        #         provider=self.provider_name,
        #         model_type=self.model_type.value,
        #         model=model,
        #         credentials=credentials or {},
        #     )
        #
        #     if schema:
        #         contexts.plugin_model_schemas.get()[cache_key] = schema

        return schema