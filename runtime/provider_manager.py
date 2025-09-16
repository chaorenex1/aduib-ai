import json

from models.provider import Provider
from .entities.model_entities import AIModelEntity
from .entities.provider_entities import ProviderEntity, ProviderConfig, ProviderSDKType
from .providers.model_provider_factory import ModelProviderFactory


class ProviderManager:

    def __init__(self):
        self.provider_factory =ModelProviderFactory()

    def get_provider_entity(self,provider: Provider, model_list: list[AIModelEntity]) -> ProviderEntity:
        """
        Get provider entity
        :return: provider entity
        """
        return ProviderEntity(
            provider=provider.name,
            supported_model_types=json.loads(provider.support_model_type),
            provider_credential=ProviderConfig(provider=provider.name,sdk_type=ProviderSDKType.value_of(provider.provider_type),credentials=json.loads(provider.provider_config)),
        models= model_list
        )