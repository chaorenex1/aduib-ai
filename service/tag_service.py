"""Tag management service for memory custom tags."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import and_, or_

from models.engine import get_db
from models.memory_tags import MemoryTagAssociation, UserCustomTag

logger = logging.getLogger(__name__)


def _tag_to_dict(tag: UserCustomTag) -> dict:
    """Serialize a tag ORM object to a plain dict (must be called inside an open session)."""
    return {
        "id": str(tag.id),
        "name": tag.name,
        "description": tag.description,
        "user_id": tag.user_id,
        "color": tag.color,
        "parent_id": str(tag.parent_id) if tag.parent_id else None,
        "is_active": tag.is_active,
        "is_system": tag.is_system,
        "usage_count": tag.usage_count or 0,
        "full_path": tag.get_full_path(),
        "created_at": tag.created_at.isoformat() if tag.created_at else None,
        "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
    }


def _assoc_to_dict(assoc: MemoryTagAssociation) -> dict:
    return {
        "memory_id": str(assoc.memory_id),
        "tag_id": str(assoc.tag_id),
        "assigned_by": assoc.assigned_by,
        "source": assoc.source,
        "context": assoc.context,
    }


class TagService:
    """CRUD + query for memory custom tags."""

    @staticmethod
    def get_or_create(
        name: str,
        user_id: str,
        vector: Optional[list[float]] = None,
    ) -> UserCustomTag:
        """Get existing active tag or create new one. Name is normalized to lowercase."""
        normalized = name.strip().lower()
        with get_db() as session:
            tag = (
                session.query(UserCustomTag)
                .filter(
                    UserCustomTag.user_id == user_id,
                    UserCustomTag.name == normalized,
                    UserCustomTag.is_active == True,
                )
                .first()
            )
            if tag is not None:
                session.expunge(tag)
                return tag
            tag = UserCustomTag(name=normalized, user_id=user_id, vector=vector)
            session.add(tag)
            session.commit()
            session.refresh(tag)
            session.expunge(tag)
            logger.info("Created tag: name=%s, user=%s", normalized, user_id)
            return tag

    @staticmethod
    def find_similar(
        vector: list[float],
        user_id: str,
        threshold: float = 0.92,
    ) -> Optional[UserCustomTag]:
        """Find the closest active tag by cosine similarity (<=>).

        Returns the matched tag name if similarity >= threshold, else None.
        """
        from sqlalchemy import Float, select

        distance_threshold = 1.0 - threshold
        vector_str = f"[{','.join(map(str, vector))}]"
        with get_db() as session:
            stmt = (
                select(
                    UserCustomTag,
                    UserCustomTag.vector.op("<=>", return_type=Float)(vector_str).label("distance"),
                )
                .where(
                    UserCustomTag.user_id == user_id,
                    UserCustomTag.is_active == True,
                    UserCustomTag.vector.isnot(None),
                )
                .order_by("distance")
                .limit(1)
            )
            row = session.execute(stmt).first()
            if row is None:
                return None
            tag, distance = row
            return tag if distance <= distance_threshold else None

    @staticmethod
    def create_tag(
        name: str,
        user_id: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> dict:
        """Create a new custom tag. Raises ValueError if name already exists for user."""
        with get_db() as session:
            existing = (
                session.query(UserCustomTag)
                .filter(
                    and_(
                        UserCustomTag.user_id == user_id,
                        UserCustomTag.name == name.lower(),
                        UserCustomTag.is_active == True,
                    )
                )
                .first()
            )
            if existing:
                raise ValueError(f"Tag '{name}' already exists for user")

            if parent_id:
                parent = (
                    session.query(UserCustomTag)
                    .filter(and_(UserCustomTag.id == parent_id, UserCustomTag.user_id == user_id))
                    .first()
                )
                if not parent:
                    raise ValueError(f"Parent tag not found: {parent_id}")

            tag = UserCustomTag(
                name=name.lower(),
                description=description,
                user_id=user_id,
                color=color,
                parent_id=parent_id,
            )
            session.add(tag)
            session.commit()
            session.refresh(tag)
            return _tag_to_dict(tag)

    @staticmethod
    def get_tag(tag_id: str) -> Optional[dict]:
        """Get a tag by ID. Returns None if not found."""
        with get_db() as session:
            tag = session.query(UserCustomTag).filter(UserCustomTag.id == tag_id).first()
            if tag is None:
                return None
            return _tag_to_dict(tag)

    @staticmethod
    def get_user_tags(
        user_id: str,
        include_inactive: bool = False,
        parent_id: Optional[str] = None,
    ) -> list[dict]:
        """Get all tags for a user."""
        with get_db() as session:
            q = session.query(UserCustomTag).filter(UserCustomTag.user_id == user_id)
            if not include_inactive:
                q = q.filter(UserCustomTag.is_active == True)
            if parent_id is not None:
                q = q.filter(UserCustomTag.parent_id == parent_id)
            tags = q.order_by(UserCustomTag.name).all()
            return [_tag_to_dict(t) for t in tags]

    @staticmethod
    def update_tag(tag_id: str, **updates) -> Optional[dict]:
        """Update a tag. Returns None if not found."""
        with get_db() as session:
            tag = session.query(UserCustomTag).filter(UserCustomTag.id == tag_id).first()
            if tag is None:
                return None
            for key, value in updates.items():
                if hasattr(tag, key) and value is not None:
                    setattr(tag, key, value)
            session.commit()
            session.refresh(tag)
            return _tag_to_dict(tag)

    @staticmethod
    def delete_tag(tag_id: str) -> bool:
        """Soft delete a tag (mark as inactive). Returns False if not found."""
        with get_db() as session:
            tag = session.query(UserCustomTag).filter(UserCustomTag.id == tag_id).first()
            if tag is None:
                return False
            tag.is_active = False
            session.commit()
            return True

    @staticmethod
    def assign_tag_to_memory(
        memory_id: str,
        tag_id: str,
        assigned_by: str,
        source: str = "manual",
        context: Optional[str] = None,
    ) -> dict:
        """Assign a tag to a memory (upsert). Returns the association dict."""
        with get_db() as session:
            existing = (
                session.query(MemoryTagAssociation)
                .filter(
                    and_(
                        MemoryTagAssociation.memory_id == memory_id,
                        MemoryTagAssociation.tag_id == tag_id,
                    )
                )
                .first()
            )

            if existing:
                existing.source = source
                existing.context = context
                session.commit()
                session.refresh(existing)
                return _assoc_to_dict(existing)

            assoc = MemoryTagAssociation(
                memory_id=memory_id,
                tag_id=tag_id,
                assigned_by=assigned_by,
                source=source,
                context=context,
            )
            session.add(assoc)

            tag = session.query(UserCustomTag).filter(UserCustomTag.id == tag_id).first()
            if tag:
                tag.usage_count = (tag.usage_count or 0) + 1

            session.commit()
            session.refresh(assoc)
            return _assoc_to_dict(assoc)

    @staticmethod
    def remove_tag_from_memory(memory_id: str, tag_id: str) -> bool:
        """Remove a tag from a memory. Returns False if association not found."""
        with get_db() as session:
            assoc = (
                session.query(MemoryTagAssociation)
                .filter(
                    and_(
                        MemoryTagAssociation.memory_id == memory_id,
                        MemoryTagAssociation.tag_id == tag_id,
                    )
                )
                .first()
            )
            if not assoc:
                return False

            session.delete(assoc)

            tag = session.query(UserCustomTag).filter(UserCustomTag.id == tag_id).first()
            if tag and tag.usage_count > 0:
                tag.usage_count -= 1

            session.commit()
            return True

    @staticmethod
    def get_memory_tags(memory_id: str) -> list[dict]:
        """Get all tags assigned to a memory."""
        with get_db() as session:
            tags = (
                session.query(UserCustomTag)
                .join(
                    MemoryTagAssociation,
                    UserCustomTag.id == MemoryTagAssociation.tag_id,
                )
                .filter(MemoryTagAssociation.memory_id == memory_id)
                .all()
            )
            return [_tag_to_dict(t) for t in tags]

    @staticmethod
    def get_memories_by_tag(tag_id: str) -> list[dict]:
        """Get all memory-tag associations for a tag."""
        with get_db() as session:
            assocs = session.query(MemoryTagAssociation).filter(MemoryTagAssociation.tag_id == tag_id).all()
            return [_assoc_to_dict(a) for a in assocs]

    @staticmethod
    def search_tags(user_id: str, query: str, limit: int = 20) -> list[dict]:
        """Search tags by name or description."""
        with get_db() as session:
            pattern = f"%{query.lower()}%"
            tags = (
                session.query(UserCustomTag)
                .filter(
                    and_(
                        UserCustomTag.user_id == user_id,
                        UserCustomTag.is_active == True,
                        or_(
                            UserCustomTag.name.like(pattern),
                            UserCustomTag.description.like(pattern),
                        ),
                    )
                )
                .limit(limit)
                .all()
            )
            return [_tag_to_dict(t) for t in tags]

    @staticmethod
    def get_tag_stats(user_id: str) -> dict:
        """Get tag usage statistics."""
        with get_db() as session:
            total_tags = session.query(UserCustomTag).filter(UserCustomTag.user_id == user_id).count()

            active_tags = (
                session.query(UserCustomTag)
                .filter(and_(UserCustomTag.user_id == user_id, UserCustomTag.is_active == True))
                .count()
            )

            system_tags = (
                session.query(UserCustomTag)
                .filter(and_(UserCustomTag.user_id == user_id, UserCustomTag.is_system == True))
                .count()
            )

            most_used = (
                session.query(UserCustomTag)
                .filter(and_(UserCustomTag.user_id == user_id, UserCustomTag.is_active == True))
                .order_by(UserCustomTag.usage_count.desc())
                .limit(10)
                .all()
            )

            return {
                "total_tags": total_tags,
                "active_tags": active_tags,
                "system_tags": system_tags,
                "user_tags": total_tags - system_tags,
                "most_used_tags": [
                    {
                        "id": str(t.id),
                        "name": t.name,
                        "usage_count": t.usage_count,
                        "full_path": t.get_full_path(),
                    }
                    for t in most_used
                ],
                "tag_hierarchy_depth": 0,
            }
