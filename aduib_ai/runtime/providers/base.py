from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from ..entities.model_entities import AIModelEntity
from ..entities.provider_entities import ProviderEntity


class AiModel(BaseModel):
    model_type: str=Field(description="Model type")
    provider_name: str=Field(description="Provider name")
    model_provider: ProviderEntity=Field(description="Model provider")