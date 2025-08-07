from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from .error.error import ModelNotFound
from ..models import get_db
from ..models.model import Model


class ModelService:

    @staticmethod
    def get_model(model_name:str, session: Session = Depends(get_db)) -> Optional[Model]:
        """
        Get model by name.
        :param model_name: model name
        :param session: database session
        :return: model
        """
        model = session.query(Model).filter_by(name=model_name).first()
        if not model:
            raise ModelNotFound("Model not found")
        return model


    @staticmethod
    def create_model(model_name:str, provider_name:str, model_type:str,max_tokens:int, model_config:dict,model_feature:dict, session: Session = Depends(get_db)) -> Optional[Model]:
        """
        Create model by name.
        :param model_name: model name
        :param provider_name: provider name
        :param model_type: model type
        :param max_tokens: max tokens
        :param model_config: model config
        :param model_feature: model feature
        :param session: database session
        :return: model
        """
        model = Model(name=model_name, provider_name=provider_name, type=model_type,max_tokens=max_tokens, model_params=model_config,feature=model_feature)
        session.add(model)
        session.commit()
        return model


    @staticmethod
    def delete_model(model_name:str, session: Session = Depends(get_db)) -> Optional[Model]:
        """
        Delete model by name.
        :param model_name: model name
        :param session: database session
        :return: model
        """
        model = session.query(Model).filter_by(name=model_name).first()
        if not model:
            return None
        session.delete(model)
        session.commit()
        return model
