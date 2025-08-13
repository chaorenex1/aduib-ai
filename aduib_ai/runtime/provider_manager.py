import json

from .entities.provider_entities import ProviderEntity, ProviderConfig, ProviderSDKType
from .providers.model_provider_factory import ModelProviderFactory
from models.provider import Provider
from service.provider_service import ProviderService


class ProviderManager:

    def __init__(self):
        self.provider_factory =ModelProviderFactory()

    def get_provider_entity(self,provider_name:str) -> ProviderEntity:
        """
        Get provider entity
        :return: provider entity
        """
        provider:Provider = ProviderService.get_provider(provider_name)
        return ProviderEntity(
            provider=provider.name,
            supported_model_types=json.load(provider.support_model_type),
            provider_credential=ProviderConfig(provider=provider.name,sdk_type=ProviderSDKType.value_of(provider.provider_type),credentials=json.loads(provider.provider_config)),
        )