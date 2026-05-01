from fastapi import APIRouter

from .auth import api_key, user_auth
from .chat import completion
from .mcp import mcp, mcp_server
from .model import model

api_router = APIRouter()
api_router.include_router(completion.router)

# auth
api_router.include_router(api_key.router)
api_router.include_router(user_auth.router)

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
from .agent import agent, messages, sessions, tooling

api_router.include_router(agent.router)
api_router.include_router(messages.router)
api_router.include_router(sessions.router)
api_router.include_router(tooling.router)

# task cache (Orchestrator integration)
from .task_cache import task_cache

api_router.include_router(task_cache.router)

# health check
from .common import health

api_router.include_router(health.router)

# programmer memory
from .memory import conversations, feedback, memories, projects, search, tasks

api_router.include_router(conversations.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(memories.router)
api_router.include_router(search.router)
api_router.include_router(feedback.router)

# memory tags
from .memory import tags

api_router.include_router(tags.router)

# file upload/download
from .file import file

api_router.include_router(file.router)
