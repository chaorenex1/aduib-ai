from fastapi import APIRouter

from .auth import api_key
from .chat import completion
from .model import model

api_router = APIRouter()
api_router.include_router(completion.router)

#auth
api_router.include_router(api_key.router)

#models
api_router.include_router(model.router)