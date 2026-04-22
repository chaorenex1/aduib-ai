from fastapi import APIRouter

from controllers.common.base import api_endpoint

router = APIRouter(tags=["health"])


@router.get("/health")
@api_endpoint()
async def health_check():
    """
    Health check endpoint for service availability monitoring
    Returns 200 OK if service is running
    """
    return {"status": "healthy", "service": "aduib-ai"}
