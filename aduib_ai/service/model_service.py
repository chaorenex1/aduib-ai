import json
from typing import Optional

from controllers.params import CreateModelRequest, ModelCard, ModelList
from models import Provider
from models.engine import get_db
from models.model import Model
from runtime.entities.model_entities import AIModelEntity, ModelFeature, ModelType, PriceConfig
from .error.error import ModelNotFound, ModelProviderNotFound


def get_model_features(model: Model) -> list[ModelFeature]:
    """
    Get model features
    :param model: Model
    :return: list[ModelFeature]
    """
    if not model.feature:
        return []
    return [ModelFeature(feature) for feature in json.loads(model.feature)]

class ModelService:

    @staticmethod
    def get_model(model_name:str) -> Optional[Model]:
        """
        Get model by name.
        :param model_name: model name
        :param session: database session
        :return: model
        """
        with get_db() as session:
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
        with get_db() as session:
            provider:Optional[Provider]=session.query(Provider).filter_by(name=req.provider_name).first()
            if not provider:
                raise ModelProviderNotFound("Provider not found")
            model = Model(name=req.model_name,
                          provider_name=req.provider_name,
                          type=req.model_type,
                          max_tokens=req.max_tokens,
                          model_params=json.dumps(req.model_configs),
                          feature=json.dumps(req.model_feature),
                          input_price=req.input_price,
                            output_price=req.output_price,
                          provider_id=provider.id)
            session.add(model)
            session.commit()
        return model


    @staticmethod
    def delete_model(model_name:str) -> Optional[Model]:
        """
        Delete model by name.
        :param model_name: model name
        :param session: database session
        :return: model
        """
        with get_db() as session:
            model = session.query(Model).filter_by(name=model_name).first()
            if not model:
                return None
            session.delete(model)
            session.commit()
        return model

    @staticmethod
    def get_models()-> Optional[ModelList]:
        """
        Get all models.
        :return: list of models
        """
        with get_db() as session:
            models = session.query(Model).all()
            if not models:
                return None
            models = [ModelCard(id=model.name,
                                root=model.provider_name+"/"+model.name,
                                         object="model",
                                         created=int(model.created_at.timestamp()),
                                         owned_by=model.provider_name,max_model_len=model.max_tokens) for model in models]
            return ModelList(object="list", data=models)


    @staticmethod
    def get_ai_models(provider_name:str)-> Optional[list[AIModelEntity]]:
        """
        Get all AI models.
        :return: list of AI models
        """
        with get_db() as session:
            models = session.query(Model).filter_by(provider_name=provider_name).all()
            if not models:
                return []
            return [AIModelEntity(model=model.name, model_type=ModelType.value_of(model.type),
                           features=get_model_features(model), model_properties=json.loads(model.model_params),
                           parameter_rules=[], pricing=PriceConfig(
                    input=model.input_price,
                    output=model.output_price), deprecated=False) for model in models]

    @staticmethod
    def get_ai_model(model_name:str) -> Optional[AIModelEntity]:
        """
        Get AI model by name and provider.
        :param model_name: model name
        :param provider_name: provider name
        :return: AIModelEntity
        """
        with get_db() as session:
            model = session.query(Model).filter_by(name=model_name).first()
            if not model:
                return None
            return AIModelEntity(model=model.name, model_type=ModelType.value_of(model.type),
                           features=get_model_features(model), model_properties=json.loads(model.model_params),
                           parameter_rules=[], pricing=PriceConfig(
                    input=model.input_price,
                    output=model.output_price,currency=model.currency), deprecated=False)
