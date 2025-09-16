import json
from typing import Optional

from models.engine import get_db
from models.provider import Provider
from service.error.error import ModelProviderNotFound


class ProviderService:
    @staticmethod
    def get_provider(provider_name: str) -> Optional[Provider]:
        """
        Get provider by name.
        :param provider_name: provider name
        :param session: database session
        :return: provider
        """
        with get_db() as session:
            provider = session.query(Provider).filter(Provider.name == provider_name).first()
            if not provider:
                raise ModelProviderNotFound("Provider not found")
        return provider

    @staticmethod
    def create_provider(
        provider_name: str, support_model_types: list[str], provider_type: str, provider_config: dict
    ) -> Optional[Provider]:
        """
        Create provider by name.
        :param provider_name: provider name
        :param support_model_types: support model types
        :param provider_type: provider type
        :param provider_config: provider config
        :param session: database session
        :return: provider
        """
        with get_db() as session:
            if support_model_types is None:
                support_model_types = {}
            if provider_config is None:
                provider_config = {}
            provider = Provider(
                name=provider_name,
                support_model_type=json.dumps(support_model_types),
                provider_type=provider_type,
                provider_config=json.dumps(provider_config),
            )
            session.add(provider)
            session.commit()
        return provider

    @staticmethod
    def delete_provider(provider: str) -> Optional[Provider] | None:
        """
        Delete provider by name.
        :param provider: provider name
        :param session: database session
        :return: provider
        """
        with get_db() as session:
            provider = session.query(Provider).filter(Provider.name == provider).first()
            if not provider:
                return None
            session.delete(provider)
            session.commit()
        return provider
