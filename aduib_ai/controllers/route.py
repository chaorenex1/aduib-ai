from fastapi import APIRouter

from .auth import api_key
from .chat import completion

api_router = APIRouter()

# api_router.include_router(openai_route.router)
# api_router.include_router(ollama_route.router)
api_router.include_router(completion.router)

#auth
api_router.include_router(api_key.router)