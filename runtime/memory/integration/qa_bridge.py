"""QA Memory Bridge for integration with UnifiedMemoryManager."""
from __future__ import annotations

from typing import Any, Optional

from runtime.memory.manager import UnifiedMemoryManager
from runtime.memory.types.base import Memory, MemoryType, MemoryMetadata, MemoryScope


class QAMemoryBridge:
    """Bridge between QA Memory and Unified Memory systems."""

    def __init__(self, manager: UnifiedMemoryManager) -> None:
        """Initialize QA Memory Bridge.

        Args:
            manager: UnifiedMemoryManager instance for storage and retrieval.
        """
        self._manager = manager

    @staticmethod
    def qa_record_to_memory(record_data: dict[str, Any]) -> Memory:
        """Convert QA record to Memory entity.

        Args:
            record_data: QA record dictionary containing question, answer, etc.

        Returns:
            Memory entity for unified storage.
        """
        question = record_data.get("question", "")
        answer = record_data.get("answer", "")
        project_id = record_data.get("project_id", "")
        tags = record_data.get("tags", [])
        trust_score = record_data.get("trust_score", 0.5)

        # Format content as Q&A pair
        content = f"Q: {question}\nA: {answer}"

        # Build metadata
        metadata = MemoryMetadata(
            scope=MemoryScope.PROJECT,
            source="qa",
            tags=tags.copy() if tags else [],
            extra={
                "project_id": project_id,
                "trust_score": trust_score
            }
        )

        # Create Memory with importance mapped from trust_score
        memory = Memory(
            type=MemoryType.SEMANTIC,
            content=content,
            metadata=metadata,
            importance=trust_score
        )

        return memory

    @staticmethod
    def memory_to_qa_dict(memory: Memory) -> dict[str, Any]:
        """Convert Memory back to QA-compatible dict.

        Args:
            memory: Memory entity from unified storage.

        Returns:
            QA-compatible dictionary.
        """
        # Parse Q&A from content
        lines = memory.content.strip().split("\n", 1)
        question = lines[0][3:] if len(lines) >= 1 and lines[0].startswith("Q: ") else ""
        answer = lines[1][3:] if len(lines) >= 2 and lines[1].startswith("A: ") else ""

        # Extract metadata
        project_id = memory.metadata.extra.get("project_id", "")
        trust_score = memory.metadata.extra.get("trust_score", memory.importance)

        return {
            "question": question,
            "answer": answer,
            "project_id": project_id,
            "tags": memory.metadata.tags.copy(),
            "trust_score": trust_score
        }

    async def store_qa(
        self,
        question: str,
        answer: str,
        project_id: str,
        tags: Optional[list[str]] = None,
        trust_score: float = 0.5
    ) -> str:
        """Store QA pair through unified memory manager.

        Args:
            question: Question text.
            answer: Answer text.
            project_id: Project identifier.
            tags: Optional tags list.
            trust_score: Trust/confidence score [0.0, 1.0].

        Returns:
            Memory ID.
        """
        record_data = {
            "question": question,
            "answer": answer,
            "project_id": project_id,
            "tags": tags or [],
            "trust_score": trust_score
        }

        memory = self.qa_record_to_memory(record_data)
        memory_id = await self._manager.store(memory)
        return memory_id

    async def search_qa(
        self,
        query: str,
        project_id: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Search QA pairs through unified memory manager.

        Args:
            query: Search query string.
            project_id: Project identifier for filtering.
            limit: Maximum number of results.

        Returns:
            List of QA-compatible result dictionaries with scores.
        """
        # Search with SEMANTIC type filter
        results = await self._manager.search(
            query=query,
            memory_types=[MemoryType.SEMANTIC],
            scope=MemoryScope.PROJECT,
            limit=limit
        )

        # Convert results to QA format and filter by project
        qa_results = []
        for result in results:
            if result.memory.metadata.extra.get("project_id") == project_id:
                qa_dict = self.memory_to_qa_dict(result.memory)
                qa_dict["score"] = result.score
                qa_results.append(qa_dict)

        return qa_results

    async def update_trust(self, memory_id: str, trust_delta: float) -> bool:
        """Update trust score for a memory.

        Args:
            memory_id: Memory identifier.
            trust_delta: Change in trust score.

        Returns:
            True if update succeeded, False otherwise.
        """
        # Get current memory
        memory = await self._manager.get(memory_id)
        if memory is None:
            return False

        # Calculate new trust score with clamping
        current_trust = memory.importance
        new_trust = max(0.0, min(1.0, current_trust + trust_delta))

        # Update both importance and metadata trust score
        updates = {
            "importance": new_trust,
            "metadata.extra.trust_score": new_trust
        }

        result = await self._manager.update(memory_id, updates)
        return result is not None

    async def sync_from_records(self, records: list[dict[str, Any]]) -> int:
        """Batch import existing QA records into unified memory.

        Args:
            records: List of QA record dictionaries.

        Returns:
            Number of successfully synced records.
        """
        synced_count = 0

        for record in records:
            try:
                memory = self.qa_record_to_memory(record)
                await self._manager.store(memory)
                synced_count += 1
            except Exception:
                # Continue with remaining records on error
                pass

        return synced_count