import json
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..models import get_db
from ..models.provider import Provider
from ..utils.snowflake_id import id_generator


class ProviderService:

    @staticmethod
    def get_provider(provider_name: str,session: Session = Depends(get_db))->Optional[Provider]:
        """
        Get provider by name.
        :param provider_name: provider name
        :param session: database session
        :return: provider
        """
        return session.query(Provider).filter(Provider.name == provider_name).first()


    @staticmethod
    def create_provider(provider_name: str, support_model_types:dict,provider_type:str,provider_config:dict, session: Session = Depends(get_db))->Optional[Provider]:
        """
        Create provider by name.
        :param provider_name: provider name
        :param support_model_types: support model types
        :param provider_type: provider type
        :param provider_config: provider config
        :param session: database session
        :return: provider
        """
        if support_model_types is None:
            support_model_types = {}
        if provider_config is None:
            provider_config = {}
        provider = Provider(id=id_generator.generate(),
                            name=provider_name,
                            support_model_type=json.dumps(support_model_types),provider_type=provider_type,provider_config=json.dumps(provider_config))
        session.add(provider)
        session.commit()
        return provider

    @staticmethod
    def delete_provider(provider: str,session: Session = Depends(get_db))->Optional[Provider]|None:
        """
        Delete provider by name.
        :param provider: provider name
        :param session: database session
        :return: provider
        """
        provider = session.query(Provider).filter(Provider.name == provider).first()
        if not provider:
            return None
        session.delete(provider)
        session.commit()
        return provider
