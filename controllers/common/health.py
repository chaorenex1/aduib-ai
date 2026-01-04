from fastapi import APIRouter
from controllers.common.base import BaseResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint for service availability monitoring
    Returns 200 OK if service is running
    """
    return BaseResponse.ok({"status": "healthy", "service": "aduib-ai"})
