"""Tests for memory custom tags functionality."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.orm import Session, relationship
from sqlalchemy import create_engine, Column, String, Text, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.declarative import declarative_base

# Create a test-specific base for SQLite compatibility
TestBase = declarative_base()


class TestUserCustomTag(TestBase):
    """Test-compatible version of UserCustomTag for SQLite."""

    __tablename__ = "user_custom_tags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(String(100), nullable=False)
    color = Column(String(7), nullable=True)
    parent_id = Column(String, ForeignKey("user_custom_tags.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    usage_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    parent = relationship("TestUserCustomTag", remote_side="TestUserCustomTag.id", backref="children")
    memory_associations = relationship("TestMemoryTagAssociation", back_populates="tag", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
        Index("idx_user_tags_user_id", "user_id"),
        Index("idx_user_tags_active", "is_active"),
        Index("idx_user_tags_parent", "parent_id"),
    )

    def get_full_path(self):
        """Get full hierarchical path of the tag."""
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return self.name

    def get_all_children(self):
        """Get all descendant tags recursively."""
        children = list(self.children)
        for child in self.children:
            children.extend(child.get_all_children())
        return children


class TestMemoryTagAssociation(TestBase):
    """Test-compatible version of MemoryTagAssociation for SQLite."""

    __tablename__ = "memory_tag_associations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_id = Column(String(100), nullable=False)
    tag_id = Column(String, ForeignKey("user_custom_tags.id"), nullable=False)
    assigned_by = Column(String(100), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence = Column(Integer, nullable=True, default=1.0)
    source = Column(String(50), default="manual", nullable=False)
    context = Column(Text, nullable=True)

    # Relationships
    tag = relationship("TestUserCustomTag", back_populates="memory_associations")

    # Constraints
    __table_args__ = (
        UniqueConstraint("memory_id", "tag_id", name="uq_memory_tag"),
        Index("idx_memory_tags_memory_id", "memory_id"),
        Index("idx_memory_tags_tag_id", "tag_id"),
        Index("idx_memory_tags_assigned_by", "assigned_by"),
        Index("idx_memory_tags_source", "source"),
    )


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create tables
    TestBase.metadata.create_all(engine)

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


# Simple TagManager for testing - using test models
class TestTagManager:
    """Simple tag manager for testing."""

    def __init__(self, db_session):
        self.db = db_session

    def create_tag(self, name, user_id, description=None, color=None, parent_id=None):
        """Create a new tag."""
        # Check if tag already exists
        existing = self.db.query(TestUserCustomTag).filter(
            TestUserCustomTag.user_id == user_id,
            TestUserCustomTag.name == name
        ).first()
        if existing:
            raise ValueError(f"Tag '{name}' already exists for user '{user_id}'")

        tag = TestUserCustomTag(
            name=name,
            user_id=user_id,
            description=description,
            color=color,
            parent_id=parent_id
        )
        self.db.add(tag)
        self.db.commit()
        return tag

    def get_tag(self, tag_id):
        """Get tag by ID."""
        return self.db.query(TestUserCustomTag).filter(TestUserCustomTag.id == tag_id).first()

    def update_tag(self, tag_id, **kwargs):
        """Update tag."""
        tag = self.get_tag(tag_id)
        if not tag:
            return None

        for key, value in kwargs.items():
            if hasattr(tag, key):
                setattr(tag, key, value)

        tag.updated_at = datetime.utcnow()
        self.db.commit()
        return tag

    def delete_tag(self, tag_id):
        """Delete tag."""
        tag = self.get_tag(tag_id)
        if not tag:
            return False

        self.db.delete(tag)
        self.db.commit()
        return True

    def assign_tag_to_memory(self, memory_id, tag_id, assigned_by, source="manual"):
        """Assign tag to memory."""
        # Check if association already exists
        existing = self.db.query(TestMemoryTagAssociation).filter(
            TestMemoryTagAssociation.memory_id == memory_id,
            TestMemoryTagAssociation.tag_id == tag_id
        ).first()
        if existing:
            raise ValueError("Tag already assigned to memory")

        association = TestMemoryTagAssociation(
            memory_id=memory_id,
            tag_id=tag_id,
            assigned_by=assigned_by,
            source=source
        )
        self.db.add(association)
        self.db.commit()
        return association

    def get_memory_tags(self, memory_id):
        """Get tags for a memory."""
        associations = self.db.query(TestMemoryTagAssociation).filter(
            TestMemoryTagAssociation.memory_id == memory_id
        ).all()
        return [assoc.tag for assoc in associations]

    def get_memories_by_tag(self, tag_id):
        """Get memories by tag."""
        return self.db.query(TestMemoryTagAssociation).filter(
            TestMemoryTagAssociation.tag_id == tag_id
        ).all()

    def get_user_tags(self, user_id, include_inactive=True):
        """Get all tags for a user."""
        query = self.db.query(TestUserCustomTag).filter(TestUserCustomTag.user_id == user_id)
        if not include_inactive:
            query = query.filter(TestUserCustomTag.is_active == True)
        return query.all()


class TestUserCustomTagModel:
    """Test UserCustomTag model functionality."""

    def test_create_custom_tag(self, db_session):
        """Test creating a custom tag."""
        tag = TestUserCustomTag(
            name="important",
            description="Important memories",
            user_id="user123",
            color="#ff0000"
        )

        db_session.add(tag)
        db_session.commit()

        # Verify tag was created
        saved_tag = db_session.query(TestUserCustomTag).filter_by(name="important").first()
        assert saved_tag is not None
        assert saved_tag.name == "important"
        assert saved_tag.description == "Important memories"
        assert saved_tag.user_id == "user123"
        assert saved_tag.color == "#ff0000"
        assert saved_tag.is_active is True

    def test_tag_hierarchy(self, db_session):
        """Test parent-child tag relationships."""
        # Create parent tag
        parent_tag = TestUserCustomTag(
            name="work",
            description="Work-related tags",
            user_id="user123"
        )
        db_session.add(parent_tag)
        db_session.commit()

        # Create child tag
        child_tag = TestUserCustomTag(
            name="meetings",
            description="Meeting memories",
            user_id="user123",
            parent_id=parent_tag.id
        )
        db_session.add(child_tag)
        db_session.commit()

        # Verify hierarchy
        assert child_tag.parent_id == parent_tag.id
        assert parent_tag in [child.parent for child in [child_tag]]

    def test_tag_unique_constraint(self, db_session):
        """Test that tag names are unique per user."""
        # Create first tag
        tag1 = TestUserCustomTag(
            name="important",
            user_id="user123"
        )
        db_session.add(tag1)
        db_session.commit()

        # Try to create duplicate tag for same user
        tag2 = TestUserCustomTag(
            name="important",
            user_id="user123"
        )
        db_session.add(tag2)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()

    def test_tag_different_users(self, db_session):
        """Test that different users can have tags with same name."""
        # Create tag for user1
        tag1 = TestUserCustomTag(
            name="important",
            user_id="user123"
        )
        db_session.add(tag1)

        # Create tag with same name for user2
        tag2 = TestUserCustomTag(
            name="important",
            user_id="user456"
        )
        db_session.add(tag2)

        db_session.commit()

        # Should not raise error - different users can have same tag names
        assert tag1.name == tag2.name
        assert tag1.user_id != tag2.user_id


class TestMemoryTagAssociationModel:
    """Test memory-tag associations."""

    def test_create_memory_tag_association(self, db_session):
        """Test associating tags with memories."""
        # Create a tag
        tag = TestUserCustomTag(
            name="urgent",
            user_id="user123"
        )
        db_session.add(tag)
        db_session.commit()

        # Create memory-tag association
        association = TestMemoryTagAssociation(
            memory_id="mem123",
            tag_id=tag.id,
            assigned_by="user123"
        )
        db_session.add(association)
        db_session.commit()

        # Verify association
        saved_assoc = db_session.query(TestMemoryTagAssociation).first()
        assert saved_assoc.memory_id == "mem123"
        assert saved_assoc.tag_id == tag.id
        assert saved_assoc.assigned_by == "user123"

    def test_multiple_tags_per_memory(self, db_session):
        """Test that a memory can have multiple tags."""
        # Create tags
        tag1 = TestUserCustomTag(name="urgent", user_id="user123")
        tag2 = TestUserCustomTag(name="work", user_id="user123")
        db_session.add_all([tag1, tag2])
        db_session.commit()

        # Associate both tags with same memory
        assoc1 = TestMemoryTagAssociation(
            memory_id="mem123",
            tag_id=tag1.id,
            assigned_by="user123"
        )
        assoc2 = TestMemoryTagAssociation(
            memory_id="mem123",
            tag_id=tag2.id,
            assigned_by="user123"
        )
        db_session.add_all([assoc1, assoc2])
        db_session.commit()

        # Verify multiple associations
        associations = db_session.query(TestMemoryTagAssociation).filter_by(memory_id="mem123").all()
        assert len(associations) == 2
        tag_ids = [assoc.tag_id for assoc in associations]
        assert tag1.id in tag_ids
        assert tag2.id in tag_ids


class TestTagManagerFunctionality:
    """Test tag management functionality."""

    def test_tag_crud_operations(self, db_session):
        """Test basic CRUD operations for tags."""
        manager = TestTagManager(db_session)

        # CREATE
        tag_data = {
            "name": "project-alpha",
            "description": "Alpha project memories",
            "color": "#00ff00",
            "user_id": "user123"
        }
        created_tag = manager.create_tag(**tag_data)

        assert created_tag.name == "project-alpha"
        assert created_tag.description == "Alpha project memories"

        # READ
        found_tag = manager.get_tag(created_tag.id)
        assert found_tag.id == created_tag.id

        # UPDATE
        updated_tag = manager.update_tag(
            created_tag.id,
            description="Updated description",
            color="#0000ff"
        )
        assert updated_tag.description == "Updated description"
        assert updated_tag.color == "#0000ff"

        # DELETE
        success = manager.delete_tag(created_tag.id)
        assert success is True

        deleted_tag = manager.get_tag(created_tag.id)
        assert deleted_tag is None

    def test_tag_memory_association(self, db_session):
        """Test associating tags with memories."""
        manager = TestTagManager(db_session)

        # Create tag
        tag = manager.create_tag(
            name="important",
            user_id="user123"
        )

        # Associate with memory
        manager.assign_tag_to_memory("mem123", tag.id, "user123")

        # Verify association
        memory_tags = manager.get_memory_tags("mem123")
        assert len(memory_tags) == 1
        assert memory_tags[0].id == tag.id

    def test_tag_filtering(self, db_session):
        """Test filtering memories by tags."""
        manager = TestTagManager(db_session)

        # Create tags
        urgent_tag = manager.create_tag(name="urgent", user_id="user123")
        work_tag = manager.create_tag(name="work", user_id="user123")

        # Associate tags with different memories
        manager.assign_tag_to_memory("mem1", urgent_tag.id, "user123")
        manager.assign_tag_to_memory("mem2", work_tag.id, "user123")
        manager.assign_tag_to_memory("mem3", urgent_tag.id, "user123")

        # Filter memories by tag
        urgent_memories = manager.get_memories_by_tag(urgent_tag.id)
        work_memories = manager.get_memories_by_tag(work_tag.id)

        assert len(urgent_memories) == 2
        assert len(work_memories) == 1

        memory_ids = [assoc.memory_id for assoc in urgent_memories]
        assert "mem1" in memory_ids
        assert "mem3" in memory_ids