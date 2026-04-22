"""Memory custom tags REST API controller."""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from controllers.common.base import ApiHttpException, api_endpoint
from service.tag_service import TagService

router = APIRouter(prefix="/api/memory/tags", tags=["Memory Tags"])


# ── Request models ──────────────────────────────────────────────────────────


class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    parent_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return v.strip().lower()


class TagUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    parent_id: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            return v.strip().lower()
        return v


class TagAssignRequest(BaseModel):
    tag_ids: list[str]
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0)
    source: Optional[str] = "manual"
    context: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/")
@api_endpoint()
def create_tag(request: TagCreateRequest, user_id: str = Query(...)):
    tag = TagService.create_tag(
        name=request.name,
        user_id=user_id,
        description=request.description,
        color=request.color,
        parent_id=request.parent_id,
    )
    return tag


@router.get("/")
@api_endpoint()
def get_user_tags(
    user_id: str = Query(...),
    include_inactive: bool = Query(False),
    parent_id: Optional[str] = Query(None),
):
    tags = TagService.get_user_tags(
        user_id=user_id,
        include_inactive=include_inactive,
        parent_id=parent_id,
    )
    return {"tags": tags, "total": len(tags)}


@router.get("/search")
@api_endpoint()
def search_tags(
    user_id: str = Query(...),
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    tags = TagService.search_tags(user_id=user_id, query=q, limit=limit)
    return {"tags": tags, "total": len(tags)}


@router.get("/stats")
@api_endpoint()
def get_tag_stats(user_id: str = Query(...)):
    stats = TagService.get_tag_stats(user_id=user_id)
    return stats


@router.get("/{tag_id}")
@api_endpoint()
def get_tag(tag_id: str):
    tag = TagService.get_tag(tag_id)
    if tag is None:
        raise ApiHttpException(status_code=404, code="tag_not_found", message="Tag not found")
    return tag


@router.patch("/{tag_id}")
@api_endpoint()
def update_tag(tag_id: str, request: TagUpdateRequest):
    updates = request.model_dump(exclude_unset=True)
    tag = TagService.update_tag(tag_id, **updates)
    if tag is None:
        raise ApiHttpException(status_code=404, code="tag_not_found", message="Tag not found")
    return tag


@router.delete("/{tag_id}")
@api_endpoint()
def delete_tag(tag_id: str):
    if not TagService.delete_tag(tag_id):
        raise ApiHttpException(status_code=404, code="tag_not_found", message="Tag not found")
    return {"message": "Tag deleted successfully"}


@router.post("/memories/{memory_id}/tags")
@api_endpoint()
def assign_tags_to_memory(
    memory_id: str,
    request: TagAssignRequest,
    assigned_by: str = Query(...),
):
    associations = [
        TagService.assign_tag_to_memory(
            memory_id=memory_id,
            tag_id=tag_id,
            assigned_by=assigned_by,
            confidence=request.confidence,
            source=request.source,
            context=request.context,
        )
        for tag_id in request.tag_ids
    ]
    return {"associations": associations, "total": len(associations)}


@router.delete("/memories/{memory_id}/tags/{tag_id}")
@api_endpoint()
def remove_tag_from_memory(memory_id: str, tag_id: str):
    if not TagService.remove_tag_from_memory(memory_id=memory_id, tag_id=tag_id):
        raise ApiHttpException(status_code=404, code="tag_association_not_found", message="Tag association not found")
    return {"message": "Tag removed from memory"}


@router.get("/memories/{memory_id}/tags")
@api_endpoint()
def get_memory_tags(memory_id: str):
    tags = TagService.get_memory_tags(memory_id=memory_id)
    return {"tags": tags, "total": len(tags)}
