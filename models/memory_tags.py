"""Memory custom tags data models."""

import datetime

from pgvecto_rs.sqlalchemy import VECTOR
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class UserCustomTag(Base):
    """User-defined custom tag for memory classification."""

    __tablename__ = "user_custom_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(String(100), nullable=False, doc="Tag name")
    description = Column(Text, nullable=True, doc="Tag description")
    user_id = Column(String(100), nullable=False, doc="Owner user ID")
    color = Column(String(7), nullable=True, doc="Tag color in hex format (#RRGGBB)")
    vector = Column(VECTOR(4096), nullable=True, comment="embedding vector")
    # Hierarchy support
    parent_id = Column(UUID(as_uuid=True), ForeignKey("user_custom_tags.id"), nullable=True, doc="Parent tag ID")

    # Tag properties
    is_active = Column(Boolean, default=True, nullable=False, doc="Whether tag is active")
    is_system = Column(Boolean, default=False, nullable=False, doc="Whether tag is system-defined")

    # Metadata
    usage_count = Column(Integer, nullable=True, default=0, doc="Number of times tag is used")
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, nullable=False)

    # Relationships
    parent = relationship("UserCustomTag", remote_side="UserCustomTag.id", backref="children")
    memory_associations = relationship("MemoryTagAssociation", back_populates="tag", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
        Index("idx_user_tags_user_id", "user_id"),
        Index("idx_user_tags_active", "is_active"),
        Index("idx_user_tags_parent", "parent_id"),
        Index(
            "idx_mem_tag_vector",
            vector,
            postgresql_using="vectors",
            postgresql_with={
                "options": """$$optimizing.optimizing_threads = 30
                                    segment.max_growing_segment_size = 2000
                                    segment.max_sealed_segment_size = 30000000
                                    [indexing.hnsw]
                                    m=30
                                    ef_construction=500$$"""
            },
            postgresql_ops={"vector": "vector_l2_ops"},
        ),
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

    def get_all_children(self) -> list["UserCustomTag"]:
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
    assigned_at = Column(DateTime, default=datetime.datetime.now, nullable=False, doc="When tag was assigned")
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
            "source": self.source,
            "context": self.context,
        }
