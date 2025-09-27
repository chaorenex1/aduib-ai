from dataclasses import dataclass
from typing import Optional, Dict, Any

from pydantic import BaseModel

from models import Agent
from runtime.tool.base.tool import Tool


@dataclass
class Message:
    id: str  # 全局唯一 id，例如 "msg_0"
    user_message: str  # 用户输入的消息内容
    assistant_message: str  # 助手生成的消息内容
    prev_message_id: str
    meta: Optional[Dict[str, Any]] = None


@dataclass
class Triple:
    subject: str
    relation: str
    object: str
    meta: Optional[Dict[str, Any]] = None



class AgentTool(BaseModel):
    tool_name: str
    tool_id: str
    tool_provider_type: str


class AgentRuntimeConfig(BaseModel):
    agent:Agent
    tools: Optional[list[Tool]] = []

