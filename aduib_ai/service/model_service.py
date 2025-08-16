from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from controllers.params import CreateModelRequest
from models.engine import get_session
from .error.error import ModelNotFound, ModelProviderNotFound
from models import get_db, Provider
from models.model import Model


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
    def create_model(req: CreateModelRequest) -> Optional[Model]:
        """
        Create model by name.
        :param req: CreateModelRequest
        :return: model
        """
        with get_session() as session:
            provider:Optional[Provider]=session.query(Provider).filter_by(name=req.provider_name).first()
            if not provider:
                raise ModelProviderNotFound("Provider not found")
            model = Model(name=req.model_name,
                          provider_name=req.provider_name,
                          type=req.model_type,
                          max_tokens=req.max_tokens,
                          model_params=req.model_configs,
                          feature=req.model_feature,
                          input_price=req.input_price,
                            output_price=req.output_price,
                          provider_id=provider.id)
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
