import time
import uuid
from typing import Optional, Any

from pydantic import BaseModel, Field

from utils import random_uuid


class CreateModelRequest(BaseModel):
    model_name: str
    provider_name: str
    model_type: str
    max_tokens: int
    input_price: float | None = 0.0
    output_price: float | None = 0.0
    model_configs: dict[str, Any]| None = {}
    model_feature: list[str] | None = []


class CreateProviderRequest(BaseModel):
    provider_name: str
    supported_model_types: list[str]
    provider_type: str
    provider_config: dict[str, Any]


class ModelPermission(BaseModel):
    id: str = Field(default_factory=lambda: f"modelperm-{random_uuid()}")
    object: str = "model_permission"
    created: int = Field(default_factory=lambda: int(time.time()))
    allow_create_engine: bool = False
    allow_sampling: bool = True
    allow_logprobs: bool = True
    allow_search_indices: bool = False
    allow_view: bool = True
    allow_fine_tuning: bool = False
    organization: str = "*"
    group: Optional[str] = None
    is_blocking: bool = False


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "vllm"
    root: Optional[str] = None
    parent: Optional[str] = None
    max_model_len: Optional[int] = None
    permission: list[ModelPermission] = Field(default_factory=list)


class ModelList(BaseModel):
    object: str = "list"
    data: list[ModelCard] = Field(default_factory=list)




class MCPServerBase(BaseModel):
    server_code: str = None
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    status: Optional[str] = Field("active", pattern="^(active|inactive)$")
    parameters: Optional[str] = None

class MCPServerCreate(MCPServerBase):
    pass

class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    parameters: Optional[str] = None

class MCPServerOut(MCPServerBase):
    id: uuid.UUID