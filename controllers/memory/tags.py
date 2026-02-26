"""Memory custom tags REST API controller and management."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from models.memory_tags import UserCustomTag, MemoryTagAssociation, SYSTEM_TAG_CATEGORIES
from models.database import get_db


# Initialize router
router = APIRouter(prefix="/api/memory/tags", tags=["Memory Tags"])


# Request/Response models
class TagCreateRequest(BaseModel):
    """Request model for creating tags."""
    name: str = Field(..., min_length=1, max_length=100, description="Tag name")
    description: Optional[str] = Field(None, max_length=500, description="Tag description")
    color: Optional[str] = Field(None, regex=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    parent_id: Optional[str] = Field(None, description="Parent tag ID for hierarchy")

    @validator('name')
    def validate_name(cls, v):
        # Remove extra spaces and convert to lowercase
        return v.strip().lower()


class TagUpdateRequest(BaseModel):
    """Request model for updating tags."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, regex=r"^#[0-9A-Fa-f]{6}$")
    parent_id: Optional[str] = None
    is_active: Optional[bool] = None

    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            return v.strip().lower()
        return v


class TagAssignRequest(BaseModel):
    """Request model for assigning tags to memories."""
    tag_ids: List[str] = Field(..., description="List of tag IDs to assign")
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Assignment confidence")
    source: Optional[str] = Field("manual", description="Assignment source")
    context: Optional[str] = Field(None, description="Additional context")


class TagResponse(BaseModel):
    """Response model for tag data."""
    id: str
    name: str
    description: Optional[str]
    user_id: str
    color: Optional[str]
    parent_id: Optional[str]
    is_active: bool
    is_system: bool
    usage_count: int
    full_path: str
    created_at: str
    updated_at: str


class TagStatsResponse(BaseModel):
    """Response model for tag statistics."""
    total_tags: int
    active_tags: int
    system_tags: int
    user_tags: int
    most_used_tags: List[Dict[str, Any]]
    tag_hierarchy_depth: int


class TagManager:
    """Tag management operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_tag(
        self,
        name: str,
        user_id: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
        parent_id: Optional[str] = None
    ) -> UserCustomTag:
        """Create a new custom tag."""
        # Check if tag with same name already exists for user
        existing = self.db.query(UserCustomTag).filter(
            and_(
                UserCustomTag.user_id == user_id,
                UserCustomTag.name == name.lower(),
                UserCustomTag.is_active == True
            )
        ).first()

        if existing:
            raise ValueError(f"Tag '{name}' already exists for user")

        # Validate parent if specified
        parent = None
        if parent_id:
            parent = self.db.query(UserCustomTag).filter(
                and_(
                    UserCustomTag.id == parent_id,
                    UserCustomTag.user_id == user_id
                )
            ).first()
            if not parent:
                raise ValueError(f"Parent tag not found: {parent_id}")

        # Create new tag
        tag = UserCustomTag(
            name=name.lower(),
            description=description,
            user_id=user_id,
            color=color,
            parent_id=parent_id
        )

        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)

        return tag

    def get_tag(self, tag_id: str) -> Optional[UserCustomTag]:
        """Get a tag by ID."""
        return self.db.query(UserCustomTag).filter(
            UserCustomTag.id == tag_id
        ).first()

    def get_user_tags(
        self,
        user_id: str,
        include_inactive: bool = False,
        parent_id: Optional[str] = None
    ) -> List[UserCustomTag]:
        """Get all tags for a user."""
        query = self.db.query(UserCustomTag).filter(
            UserCustomTag.user_id == user_id
        )

        if not include_inactive:
            query = query.filter(UserCustomTag.is_active == True)

        if parent_id is not None:
            query = query.filter(UserCustomTag.parent_id == parent_id)

        return query.order_by(UserCustomTag.name).all()

    def update_tag(
        self,
        tag_id: str,
        **updates
    ) -> Optional[UserCustomTag]:
        """Update a tag."""
        tag = self.get_tag(tag_id)
        if not tag:
            return None

        # Update fields
        for key, value in updates.items():
            if hasattr(tag, key) and value is not None:
                setattr(tag, key, value)

        self.db.commit()
        self.db.refresh(tag)

        return tag

    def delete_tag(self, tag_id: str) -> bool:
        """Soft delete a tag (mark as inactive)."""
        tag = self.get_tag(tag_id)
        if not tag:
            return False

        # Mark as inactive instead of deleting
        tag.is_active = False
        self.db.commit()

        return True

    def assign_tag_to_memory(
        self,
        memory_id: str,
        tag_id: str,
        assigned_by: str,
        confidence: float = 1.0,
        source: str = "manual",
        context: Optional[str] = None
    ) -> MemoryTagAssociation:
        """Assign a tag to a memory."""
        # Check if association already exists
        existing = self.db.query(MemoryTagAssociation).filter(
            and_(
                MemoryTagAssociation.memory_id == memory_id,
                MemoryTagAssociation.tag_id == tag_id
            )
        ).first()

        if existing:
            # Update existing association
            existing.confidence = confidence
            existing.source = source
            existing.context = context
            self.db.commit()
            return existing

        # Create new association
        association = MemoryTagAssociation(
            memory_id=memory_id,
            tag_id=tag_id,
            assigned_by=assigned_by,
            confidence=confidence,
            source=source,
            context=context
        )

        self.db.add(association)

        # Update usage count
        tag = self.get_tag(tag_id)
        if tag:
            tag.usage_count = (tag.usage_count or 0) + 1

        self.db.commit()
        self.db.refresh(association)

        return association

    def remove_tag_from_memory(self, memory_id: str, tag_id: str) -> bool:
        """Remove a tag from a memory."""
        association = self.db.query(MemoryTagAssociation).filter(
            and_(
                MemoryTagAssociation.memory_id == memory_id,
                MemoryTagAssociation.tag_id == tag_id
            )
        ).first()

        if not association:
            return False

        self.db.delete(association)

        # Update usage count
        tag = self.get_tag(tag_id)
        if tag and tag.usage_count > 0:
            tag.usage_count -= 1

        self.db.commit()
        return True

    def get_memory_tags(self, memory_id: str) -> List[UserCustomTag]:
        """Get all tags assigned to a memory."""
        return self.db.query(UserCustomTag).join(
            MemoryTagAssociation,
            UserCustomTag.id == MemoryTagAssociation.tag_id
        ).filter(
            MemoryTagAssociation.memory_id == memory_id
        ).all()

    def get_memories_by_tag(self, tag_id: str) -> List[MemoryTagAssociation]:
        """Get all memories that have a specific tag."""
        return self.db.query(MemoryTagAssociation).filter(
            MemoryTagAssociation.tag_id == tag_id
        ).all()

    def search_tags(
        self,
        user_id: str,
        query: str,
        limit: int = 20
    ) -> List[UserCustomTag]:
        """Search tags by name or description."""
        search_pattern = f"%{query.lower()}%"

        return self.db.query(UserCustomTag).filter(
            and_(
                UserCustomTag.user_id == user_id,
                UserCustomTag.is_active == True,
                or_(
                    UserCustomTag.name.like(search_pattern),
                    UserCustomTag.description.like(search_pattern)
                )
            )
        ).limit(limit).all()

    def get_tag_stats(self, user_id: str) -> Dict[str, Any]:
        """Get tag usage statistics."""
        total_tags = self.db.query(UserCustomTag).filter(
            UserCustomTag.user_id == user_id
        ).count()

        active_tags = self.db.query(UserCustomTag).filter(
            and_(
                UserCustomTag.user_id == user_id,
                UserCustomTag.is_active == True
            )
        ).count()

        system_tags = self.db.query(UserCustomTag).filter(
            and_(
                UserCustomTag.user_id == user_id,
                UserCustomTag.is_system == True
            )
        ).count()

        # Most used tags
        most_used = self.db.query(UserCustomTag).filter(
            and_(
                UserCustomTag.user_id == user_id,
                UserCustomTag.is_active == True
            )
        ).order_by(UserCustomTag.usage_count.desc()).limit(10).all()

        return {
            "total_tags": total_tags,
            "active_tags": active_tags,
            "system_tags": system_tags,
            "user_tags": total_tags - system_tags,
            "most_used_tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "usage_count": tag.usage_count,
                    "full_path": tag.get_full_path()
                }
                for tag in most_used
            ]
        }


# REST API Endpoints
@router.post("/", response_model=TagResponse)
async def create_tag(
    request: TagCreateRequest,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Create a new custom tag."""
    manager = TagManager(db)

    try:
        tag = manager.create_tag(
            name=request.name,
            user_id=user_id,
            description=request.description,
            color=request.color,
            parent_id=request.parent_id
        )

        return TagResponse(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            user_id=tag.user_id,
            color=tag.color,
            parent_id=tag.parent_id,
            is_active=tag.is_active,
            is_system=tag.is_system,
            usage_count=tag.usage_count,
            full_path=tag.get_full_path(),
            created_at=tag.created_at.isoformat(),
            updated_at=tag.updated_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[TagResponse])
async def get_user_tags(
    user_id: str = Query(..., description="User ID"),
    include_inactive: bool = Query(False, description="Include inactive tags"),
    parent_id: Optional[str] = Query(None, description="Filter by parent tag"),
    db: Session = Depends(get_db)
):
    """Get all tags for a user."""
    manager = TagManager(db)

    tags = manager.get_user_tags(
        user_id=user_id,
        include_inactive=include_inactive,
        parent_id=parent_id
    )

    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            user_id=tag.user_id,
            color=tag.color,
            parent_id=tag.parent_id,
            is_active=tag.is_active,
            is_system=tag.is_system,
            usage_count=tag.usage_count,
            full_path=tag.get_full_path(),
            created_at=tag.created_at.isoformat(),
            updated_at=tag.updated_at.isoformat()
        )
        for tag in tags
    ]


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific tag by ID."""
    manager = TagManager(db)
    tag = manager.get_tag(tag_id)

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    return TagResponse(
        id=tag.id,
        name=tag.name,
        description=tag.description,
        user_id=tag.user_id,
        color=tag.color,
        parent_id=tag.parent_id,
        is_active=tag.is_active,
        is_system=tag.is_system,
        usage_count=tag.usage_count,
        full_path=tag.get_full_path(),
        created_at=tag.created_at.isoformat(),
        updated_at=tag.updated_at.isoformat()
    )


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: str,
    request: TagUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update a tag."""
    manager = TagManager(db)

    updates = request.dict(exclude_unset=True)
    tag = manager.update_tag(tag_id, **updates)

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    return TagResponse(
        id=tag.id,
        name=tag.name,
        description=tag.description,
        user_id=tag.user_id,
        color=tag.color,
        parent_id=tag.parent_id,
        is_active=tag.is_active,
        is_system=tag.is_system,
        usage_count=tag.usage_count,
        full_path=tag.get_full_path(),
        created_at=tag.created_at.isoformat(),
        updated_at=tag.updated_at.isoformat()
    )


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db)
):
    """Delete (deactivate) a tag."""
    manager = TagManager(db)

    success = manager.delete_tag(tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found")

    return {"message": "Tag deleted successfully"}


@router.post("/memories/{memory_id}/tags")
async def assign_tags_to_memory(
    memory_id: str,
    request: TagAssignRequest,
    assigned_by: str = Query(..., description="User assigning the tags"),
    db: Session = Depends(get_db)
):
    """Assign tags to a memory."""
    manager = TagManager(db)

    associations = []
    for tag_id in request.tag_ids:
        try:
            association = manager.assign_tag_to_memory(
                memory_id=memory_id,
                tag_id=tag_id,
                assigned_by=assigned_by,
                confidence=request.confidence,
                source=request.source,
                context=request.context
            )
            associations.append(association.to_dict())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to assign tag {tag_id}: {str(e)}")

    return {
        "message": f"Assigned {len(associations)} tags to memory",
        "associations": associations
    }


@router.delete("/memories/{memory_id}/tags/{tag_id}")
async def remove_tag_from_memory(
    memory_id: str,
    tag_id: str,
    db: Session = Depends(get_db)
):
    """Remove a tag from a memory."""
    manager = TagManager(db)

    success = manager.remove_tag_from_memory(memory_id, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tag association not found")

    return {"message": "Tag removed from memory"}


@router.get("/memories/{memory_id}/tags", response_model=List[TagResponse])
async def get_memory_tags(
    memory_id: str,
    db: Session = Depends(get_db)
):
    """Get all tags assigned to a memory."""
    manager = TagManager(db)
    tags = manager.get_memory_tags(memory_id)

    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            user_id=tag.user_id,
            color=tag.color,
            parent_id=tag.parent_id,
            is_active=tag.is_active,
            is_system=tag.is_system,
            usage_count=tag.usage_count,
            full_path=tag.get_full_path(),
            created_at=tag.created_at.isoformat(),
            updated_at=tag.updated_at.isoformat()
        )
        for tag in tags
    ]


@router.get("/search", response_model=List[TagResponse])
async def search_tags(
    user_id: str = Query(..., description="User ID"),
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    db: Session = Depends(get_db)
):
    """Search tags by name or description."""
    manager = TagManager(db)
    tags = manager.search_tags(user_id, q, limit)

    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            user_id=tag.user_id,
            color=tag.color,
            parent_id=tag.parent_id,
            is_active=tag.is_active,
            is_system=tag.is_system,
            usage_count=tag.usage_count,
            full_path=tag.get_full_path(),
            created_at=tag.created_at.isoformat(),
            updated_at=tag.updated_at.isoformat()
        )
        for tag in tags
    ]


@router.get("/stats", response_model=TagStatsResponse)
async def get_tag_stats(
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Get tag usage statistics."""
    manager = TagManager(db)
    stats = manager.get_tag_stats(user_id)

    return TagStatsResponse(**stats, tag_hierarchy_depth=0)  # TODO: Calculate hierarchy depth


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "memory-custom-tags"}