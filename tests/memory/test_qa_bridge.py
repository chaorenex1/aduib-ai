"""Tests for QA memory bridge integration."""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from runtime.memory.types.base import Memory, MemoryType, MemoryMetadata, MemoryScope
from runtime.memory.integration.qa_bridge import QAMemoryBridge
from runtime.memory.retrieval.engine import RetrievalResult


class TestQAMemoryBridge:
    """Test QA Memory Bridge functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Mock UnifiedMemoryManager."""
        manager = AsyncMock()
        return manager

    @pytest.fixture
    def bridge(self, mock_manager):
        """QA Memory Bridge instance."""
        return QAMemoryBridge(mock_manager)

    @pytest.fixture
    def sample_qa_record(self):
        """Sample QA record data."""
        return {
            "question": "What is Python?",
            "answer": "Python is a programming language",
            "project_id": "test-project",
            "tags": ["python", "programming"],
            "trust_score": 0.8,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

    @pytest.fixture
    def sample_memory(self):
        """Sample Memory instance."""
        return Memory(
            type=MemoryType.SEMANTIC,
            content="Q: What is Python?\nA: Python is a programming language",
            metadata=MemoryMetadata(
                scope=MemoryScope.PROJECT,
                source="qa",
                tags=["python", "programming"],
                extra={"project_id": "test-project", "trust_score": 0.8}
            ),
            importance=0.8
        )

    def test_qa_record_to_memory_conversion(self, sample_qa_record):
        """Test converting QA record to Memory."""
        # RED: Write failing test first
        memory = QAMemoryBridge.qa_record_to_memory(sample_qa_record)

        assert memory.type == MemoryType.SEMANTIC
        assert memory.content == "Q: What is Python?\nA: Python is a programming language"
        assert memory.metadata.source == "qa"
        assert memory.metadata.scope == MemoryScope.PROJECT
        assert memory.metadata.tags == ["python", "programming"]
        assert memory.importance == 0.8
        assert memory.metadata.extra["project_id"] == "test-project"
        assert memory.metadata.extra["trust_score"] == 0.8

    def test_memory_to_qa_dict_conversion(self, sample_memory):
        """Test converting Memory back to QA dict."""
        # RED: Write failing test first
        qa_dict = QAMemoryBridge.memory_to_qa_dict(sample_memory)

        assert qa_dict["question"] == "What is Python?"
        assert qa_dict["answer"] == "Python is a programming language"
        assert qa_dict["project_id"] == "test-project"
        assert qa_dict["tags"] == ["python", "programming"]
        assert qa_dict["trust_score"] == 0.8

    @pytest.mark.asyncio
    async def test_store_qa(self, bridge, mock_manager):
        """Test storing QA through bridge."""
        # RED: Write failing test first
        mock_manager.store.return_value = "memory-123"

        memory_id = await bridge.store_qa(
            question="What is Python?",
            answer="Python is a programming language",
            project_id="test-project",
            tags=["python"],
            trust_score=0.7
        )

        assert memory_id == "memory-123"
        mock_manager.store.assert_called_once()
        stored_memory = mock_manager.store.call_args[0][0]
        assert stored_memory.type == MemoryType.SEMANTIC
        assert "What is Python?" in stored_memory.content
        assert "Python is a programming language" in stored_memory.content

    @pytest.mark.asyncio
    async def test_search_qa(self, bridge, mock_manager):
        """Test searching QA through bridge."""
        # RED: Write failing test first
        mock_memory = Memory(
            type=MemoryType.SEMANTIC,
            content="Q: What is FastAPI?\nA: FastAPI is a web framework",
            metadata=MemoryMetadata(
                source="qa",
                tags=["fastapi"],
                extra={"project_id": "test-project", "trust_score": 0.6}
            ),
            importance=0.6
        )

        mock_result = RetrievalResult(memory=mock_memory, score=0.85, source="semantic")
        mock_manager.search.return_value = [mock_result]

        results = await bridge.search_qa("FastAPI", "test-project", limit=5)

        assert len(results) == 1
        result = results[0]
        assert result["question"] == "What is FastAPI?"
        assert result["answer"] == "FastAPI is a web framework"
        assert result["score"] == 0.85
        assert result["trust_score"] == 0.6

    @pytest.mark.asyncio
    async def test_update_trust(self, bridge, mock_manager, sample_memory):
        """Test updating trust score through bridge."""
        # RED: Write failing test first
        mock_manager.get.return_value = sample_memory
        mock_manager.update.return_value = sample_memory

        success = await bridge.update_trust("memory-123", 0.1)

        assert success is True
        mock_manager.update.assert_called_once_with(
            "memory-123",
            {"importance": 0.9, "metadata.extra.trust_score": 0.9}
        )

    @pytest.mark.asyncio
    async def test_update_trust_clamps_values(self, bridge, mock_manager, sample_memory):
        """Test trust score clamping."""
        # RED: Write failing test first
        sample_memory.importance = 0.9
        mock_manager.get.return_value = sample_memory
        mock_manager.update.return_value = sample_memory

        # Test upper bound clamping
        success = await bridge.update_trust("memory-123", 0.5)
        assert success is True
        mock_manager.update.assert_called_once_with(
            "memory-123",
            {"importance": 1.0, "metadata.extra.trust_score": 1.0}
        )

    @pytest.mark.asyncio
    async def test_sync_from_records(self, bridge, mock_manager):
        """Test batch sync from QA records."""
        # RED: Write failing test first
        records = [
            {
                "question": "What is Python?",
                "answer": "Python is a programming language",
                "project_id": "test",
                "tags": ["python"],
                "trust_score": 0.8
            },
            {
                "question": "What is FastAPI?",
                "answer": "FastAPI is a web framework",
                "project_id": "test",
                "tags": ["fastapi"],
                "trust_score": 0.7
            }
        ]

        mock_manager.store.return_value = "memory-id"

        count = await bridge.sync_from_records(records)

        assert count == 2
        assert mock_manager.store.call_count == 2

    def test_round_trip_conversion_preserves_data(self, sample_qa_record):
        """Test that record -> memory -> record preserves data."""
        # RED: Write failing test first
        memory = QAMemoryBridge.qa_record_to_memory(sample_qa_record)
        converted_back = QAMemoryBridge.memory_to_qa_dict(memory)

        # Core fields should be preserved
        assert converted_back["question"] == sample_qa_record["question"]
        assert converted_back["answer"] == sample_qa_record["answer"]
        assert converted_back["project_id"] == sample_qa_record["project_id"]
        assert converted_back["tags"] == sample_qa_record["tags"]
        assert converted_back["trust_score"] == sample_qa_record["trust_score"]