"""Memory custom tags data models."""

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Integer,
    UniqueConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List

from models import Base


class UserCustomTag(Base):
    """User-defined custom tag for memory classification."""

    __tablename__ = "user_custom_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(String(100), nullable=False, doc="Tag name")
    description = Column(Text, nullable=True, doc="Tag description")
    user_id = Column(String(100), nullable=False, doc="Owner user ID")
    color = Column(String(7), nullable=True, doc="Tag color in hex format (#RRGGBB)")

    # Hierarchy support
    parent_id = Column(UUID(as_uuid=True), ForeignKey("user_custom_tags.id"), nullable=True, doc="Parent tag ID")

    # Tag properties
    is_active = Column(Boolean, default=True, nullable=False, doc="Whether tag is active")
    is_system = Column(Boolean, default=False, nullable=False, doc="Whether tag is system-defined")

    # Metadata
    usage_count = Column(Integer, nullable=True, default=0, doc="Number of times tag is used")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    parent = relationship("UserCustomTag", remote_side="UserCustomTag.id", backref="children")
    memory_associations = relationship("MemoryTagAssociation", back_populates="tag", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
        Index("idx_user_tags_user_id", "user_id"),
        Index("idx_user_tags_active", "is_active"),
        Index("idx_user_tags_parent", "parent_id"),
    )

    def __repr__(self):
        return f"<UserCustomTag(id='{self.id}', name='{self.name}', user_id='{self.user_id}')>"

    def to_dict(self) -> dict:
        """Convert tag to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "color": self.color,
            "parent_id": self.parent_id,
            "is_active": self.is_active,
            "is_system": self.is_system,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_full_path(self) -> str:
        """Get full hierarchical path of the tag."""
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return self.name

    def get_all_children(self) -> List["UserCustomTag"]:
        """Get all descendant tags recursively."""
        children = list(self.children)
        for child in self.children:
            children.extend(child.get_all_children())
        return children


class MemoryTagAssociation(Base):
    """Association between memories and custom tags."""

    __tablename__ = "memory_tag_associations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    memory_id = Column(String(100), nullable=False, doc="Memory ID")
    tag_id = Column(UUID(as_uuid=True), ForeignKey("user_custom_tags.id"), nullable=False, doc="Tag ID")
    assigned_by = Column(String(100), nullable=False, doc="User who assigned the tag")

    # Assignment metadata
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False, doc="When tag was assigned")
    confidence = Column(Integer, nullable=True, default=1.0, doc="Assignment confidence (0.0-1.0)")
    source = Column(String(50), default="manual", nullable=False, doc="Assignment source (manual/auto/learned)")

    # Optional context
    context = Column(Text, nullable=True, doc="Additional context for the assignment")

    # Relationships
    tag = relationship("UserCustomTag", back_populates="memory_associations")

    # Constraints
    __table_args__ = (
        UniqueConstraint("memory_id", "tag_id", name="uq_memory_tag"),
        Index("idx_memory_tags_memory_id", "memory_id"),
        Index("idx_memory_tags_tag_id", "tag_id"),
        Index("idx_memory_tags_assigned_by", "assigned_by"),
        Index("idx_memory_tags_source", "source"),
    )

    def __repr__(self):
        return f"<MemoryTagAssociation(memory_id='{self.memory_id}', tag_id='{self.tag_id}')>"

    def to_dict(self) -> dict:
        """Convert association to dictionary."""
        return {
            "id": self.id,
            "memory_id": self.memory_id,
            "tag_id": self.tag_id,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "confidence": self.confidence,
            "source": self.source,
            "context": self.context,
        }


# Define common tag categories for system tags
SYSTEM_TAG_CATEGORIES = {
    "priority": {
        "urgent": {"color": "#ff4444", "description": "Urgent items requiring immediate attention"},
        "important": {"color": "#ff8800", "description": "Important but not urgent items"},
        "normal": {"color": "#4488ff", "description": "Normal priority items"},
        "low": {"color": "#888888", "description": "Low priority items"},
    },
    "type": {
        "question": {"color": "#44ff44", "description": "Questions and inquiries"},
        "idea": {"color": "#ffff44", "description": "Ideas and inspirations"},
        "task": {"color": "#ff44ff", "description": "Tasks and action items"},
        "note": {"color": "#44ffff", "description": "Notes and observations"},
    },
    "status": {
        "todo": {"color": "#ff6644", "description": "Items to be done"},
        "in-progress": {"color": "#ffaa00", "description": "Items currently being worked on"},
        "done": {"color": "#44aa44", "description": "Completed items"},
        "archived": {"color": "#666666", "description": "Archived items"},
    }
}