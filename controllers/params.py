import time
import uuid
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, Field

from utils import random_uuid


class CreateModelRequest(BaseModel):
    model_name: str
    provider_name: str
    model_type: str
    max_tokens: int
    input_price: Decimal | None = 0.0
    output_price: Decimal | None = 0.0
    model_configs: dict[str, Any] | None = {}
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
    server_url: str = None
    server_code: str = None
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    status: Optional[str] = Field("active", pattern="^(active|inactive)$")
    configs: Optional[str] = None
    credentials: Optional[str] = None


class MCPServerCreate(MCPServerBase):
    pass


class MCPServerUpdate(BaseModel):
    server_url: str = None
    server_code: str = None
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    status: Optional[str] = Field("active", pattern="^(active|inactive)$")
    configs: Optional[str] = None
    credentials: Optional[str] = None


class MCPServerOut(MCPServerBase):
    id: uuid.UUID


class KnowledgeBasePayload(BaseModel):
    name: str
    default_base: int = 0
    rag_type: str


class KnowledgeRetrievalPayload(BaseModel):
    query: str
    rag_type: str


class BrowserHistoryPayload(BaseModel):
    query: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class AgentCreatePayload(BaseModel):
    name: str
    model_id: str
    description: Optional[str] = ""
    prompt_template: Optional[str] = ""
    tools: Optional[list] = []
    agent_parameters: Optional[dict] = {}
