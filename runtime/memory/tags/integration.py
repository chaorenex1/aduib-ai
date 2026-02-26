"""Memory tag integration system."""

from typing import List, Optional, Dict, Set
from sqlalchemy.orm import Session

from models.memory_tags import UserCustomTag, MemoryTagAssociation
from controllers.memory.tags import TagManager


class MemoryTagIntegrator:
    """Integrates string-based tags with custom tag database records."""

    def __init__(self, db: Session):
        self.db = db
        self.tag_manager = TagManager(db)

    def resolve_tags(
        self,
        tag_names: List[str],
        user_id: str,
        auto_create: bool = True
    ) -> List[UserCustomTag]:
        """Resolve tag names to UserCustomTag objects."""
        resolved_tags = []

        for tag_name in tag_names:
            # Clean tag name
            clean_name = tag_name.strip().lower()
            if not clean_name:
                continue

            # Try to find existing tag
            existing_tag = self.db.query(UserCustomTag).filter(
                UserCustomTag.user_id == user_id,
                UserCustomTag.name == clean_name,
                UserCustomTag.is_active == True
            ).first()

            if existing_tag:
                resolved_tags.append(existing_tag)
            elif auto_create:
                # Create new tag
                try:
                    new_tag = self.tag_manager.create_tag(
                        name=clean_name,
                        user_id=user_id,
                        description=f"Auto-created tag: {clean_name}"
                    )
                    resolved_tags.append(new_tag)
                except ValueError:
                    # Tag might have been created concurrently, try to find it again
                    existing_tag = self.db.query(UserCustomTag).filter(
                        UserCustomTag.user_id == user_id,
                        UserCustomTag.name == clean_name,
                        UserCustomTag.is_active == True
                    ).first()
                    if existing_tag:
                        resolved_tags.append(existing_tag)

        return resolved_tags

    def assign_memory_tags(
        self,
        memory_id: str,
        tag_names: List[str],
        user_id: str,
        assigned_by: str,
        auto_create: bool = True
    ) -> List[MemoryTagAssociation]:
        """Assign tags to a memory by tag names."""
        if not tag_names:
            return []

        # Resolve tag names to tag objects
        tags = self.resolve_tags(tag_names, user_id, auto_create)

        # Create associations
        associations = []
        for tag in tags:
            try:
                association = self.tag_manager.assign_tag_to_memory(
                    memory_id=memory_id,
                    tag_id=tag.id,
                    assigned_by=assigned_by,
                    source="system"
                )
                associations.append(association)
            except Exception:
                # Skip if association fails (might already exist)
                continue

        return associations

    def get_memory_tag_names(self, memory_id: str) -> List[str]:
        """Get tag names for a memory."""
        tags = self.tag_manager.get_memory_tags(memory_id)
        return [tag.name for tag in tags]

    def filter_memories_by_tags(
        self,
        memory_ids: List[str],
        required_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Set[str]:
        """Filter memory IDs based on tag criteria."""
        if not required_tags and not excluded_tags:
            return set(memory_ids)

        filtered_memory_ids = set(memory_ids)

        # Filter by required tags
        if required_tags:
            required_tag_ids = []
            for tag_name in required_tags:
                tag = self.db.query(UserCustomTag).filter(
                    UserCustomTag.name == tag_name.lower(),
                    UserCustomTag.is_active == True
                ).first()
                if tag and (not user_id or tag.user_id == user_id):
                    required_tag_ids.append(tag.id)

            if required_tag_ids:
                # Get memories that have ALL required tags
                for tag_id in required_tag_ids:
                    tag_memory_ids = {
                        assoc.memory_id
                        for assoc in self.tag_manager.get_memories_by_tag(tag_id)
                    }
                    filtered_memory_ids &= tag_memory_ids

        # Filter out excluded tags
        if excluded_tags:
            excluded_tag_ids = []
            for tag_name in excluded_tags:
                tag = self.db.query(UserCustomTag).filter(
                    UserCustomTag.name == tag_name.lower(),
                    UserCustomTag.is_active == True
                ).first()
                if tag and (not user_id or tag.user_id == user_id):
                    excluded_tag_ids.append(tag.id)

            if excluded_tag_ids:
                # Remove memories that have ANY excluded tags
                for tag_id in excluded_tag_ids:
                    tag_memory_ids = {
                        assoc.memory_id
                        for assoc in self.tag_manager.get_memories_by_tag(tag_id)
                    }
                    filtered_memory_ids -= tag_memory_ids

        return filtered_memory_ids

    def suggest_tags_for_content(
        self,
        content: str,
        user_id: str,
        limit: int = 5
    ) -> List[UserCustomTag]:
        """Suggest relevant tags based on content."""
        # Simple keyword-based suggestion
        content_lower = content.lower()
        suggestions = []

        # Get user's existing tags
        user_tags = self.tag_manager.get_user_tags(user_id)

        for tag in user_tags:
            # Check if tag name appears in content
            if tag.name in content_lower:
                suggestions.append((tag, tag.name.count('') + 1))  # Simple scoring

            # Check if tag description keywords appear in content
            elif tag.description:
                desc_words = tag.description.lower().split()
                score = sum(1 for word in desc_words if word in content_lower)
                if score > 0:
                    suggestions.append((tag, score))

        # Sort by relevance score and return top suggestions
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [tag for tag, score in suggestions[:limit]]

    def get_tag_statistics(self, user_id: str) -> Dict:
        """Get comprehensive tag statistics for a user."""
        stats = self.tag_manager.get_tag_stats(user_id)

        # Add memory association statistics
        total_associations = self.db.query(MemoryTagAssociation).join(
            UserCustomTag,
            MemoryTagAssociation.tag_id == UserCustomTag.id
        ).filter(
            UserCustomTag.user_id == user_id
        ).count()

        # Get tag usage distribution
        tag_usage = {}
        user_tags = self.tag_manager.get_user_tags(user_id)
        for tag in user_tags:
            memory_count = len(self.tag_manager.get_memories_by_tag(tag.id))
            tag_usage[tag.name] = {
                "id": tag.id,
                "memory_count": memory_count,
                "usage_count": tag.usage_count,
                "full_path": tag.get_full_path()
            }

        stats.update({
            "total_associations": total_associations,
            "tag_usage_distribution": tag_usage,
            "average_tags_per_memory": total_associations / max(1, stats["active_tags"])
        })

        return stats

    def cleanup_unused_tags(self, user_id: str, dry_run: bool = True) -> Dict:
        """Clean up unused tags for a user."""
        unused_tags = []

        user_tags = self.tag_manager.get_user_tags(user_id, include_inactive=False)
        for tag in user_tags:
            memory_count = len(self.tag_manager.get_memories_by_tag(tag.id))
            if memory_count == 0 and not tag.is_system:
                unused_tags.append(tag)

        if not dry_run:
            # Actually delete unused tags
            deleted_count = 0
            for tag in unused_tags:
                if self.tag_manager.delete_tag(tag.id):
                    deleted_count += 1

            return {
                "unused_tags_found": len(unused_tags),
                "tags_deleted": deleted_count,
                "dry_run": False
            }

        return {
            "unused_tags_found": len(unused_tags),
            "unused_tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "created_at": tag.created_at.isoformat()
                }
                for tag in unused_tags
            ],
            "dry_run": True
        }