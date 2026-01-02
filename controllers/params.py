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


class QASearchPayload(BaseModel):
    project_id: str = Field(..., description="Project/workspace identifier")
    query: str
    limit: int = Field(6, ge=1, le=20)
    min_score: float = Field(0.2, ge=0.0, le=1.0)


class QACandidatePayload(BaseModel):
    project_id: str
    question: str
    answer: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    author: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class QAReferencePayload(BaseModel):
    qa_id: str
    shown: bool = True
    used: bool = False
    message_id: str | None = None
    context: str | None = None


class QAHitsPayload(BaseModel):
    project_id: str
    references: list[QAReferencePayload] = Field(default_factory=list)


class QAValidationPayload(BaseModel):
    project_id: str
    qa_id: str
    result: str | None = None
    signal_strength: str | None = None
    success: bool | None = None
    strong_signal: bool = False
    source: str | None = None
    context: dict[str, Any] | None = None
    client: dict[str, Any] | None = None
    ts: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class QAExpirePayload(BaseModel):
    batch_size: int = Field(default=200, ge=1, le=1000)


class TaskGradePayload(BaseModel):
    prompt: str

class TaskGradeResult(BaseModel):
    task_level: str
    reason: str
    recommended_model: str
    recommended_model_provider: str
    confidence: float
