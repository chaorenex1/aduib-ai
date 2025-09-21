from fastapi import APIRouter

from .auth import api_key
from .chat import completion
from .mcp import mcp_server, mcp
from .model import model

api_router = APIRouter()
api_router.include_router(completion.router)

# auth
api_router.include_router(api_key.router)

# models
api_router.include_router(model.router)

# mcp_server
api_router.include_router(mcp_server.router)

# mcp
api_router.include_router(mcp.router)

# web_memo
from .web_memo import web_memo

api_router.include_router(web_memo.router)

# document
from .document import document

api_router.include_router(document.router)

# knowledge
from .knowledge import knowledge
api_router.include_router(knowledge.router)

# agent
from .agent import agent
api_router.include_router(agent.router)
