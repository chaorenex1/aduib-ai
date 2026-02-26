"""Standalone tests for memory classification configuration."""

import pytest
from pathlib import Path
import tempfile
import yaml
import asyncio
import sys
import os

# Add project root to Python path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.memory.classification.config import (
    ClassificationConfig,
    ClassificationConfigManager,
    ProjectPattern,
    ModulePattern,
    CandidatePattern,
)


class TestClassificationConfig:
    """Test configuration data models."""

    def test_project_pattern_creation(self):
        """Test ProjectPattern model."""
        pattern = ProjectPattern(
            pattern="llm-platform",
            project="LLM Platform",
            confidence=1.0,
            source="manual"
        )

        assert pattern.pattern == "llm-platform"
        assert pattern.project == "LLM Platform"
        assert pattern.confidence == 1.0
        assert pattern.source == "manual"

    def test_classification_config_structure(self):
        """Test complete ClassificationConfig structure."""
        config = ClassificationConfig(
            project_patterns=[
                ProjectPattern(pattern="llm", project="LLM Platform", confidence=1.0, source="manual")
            ],
            module_patterns=[
                ModulePattern(pattern="runtime/memory", module="memory", confidence=1.0, source="manual")
            ],
            candidate_patterns=[
                CandidatePattern(pattern="mobile-app", project="Mobile App", frequency=3, confidence=0.8)
            ],
            auto_learning=True,
            confidence_threshold=0.8
        )

        assert len(config.project_patterns) == 1
        assert len(config.module_patterns) == 1
        assert len(config.candidate_patterns) == 1
        assert config.auto_learning is True
        assert config.confidence_threshold == 0.8


class TestClassificationConfigManager:
    """Test configuration manager."""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file for testing."""
        config_data = {
            "project_patterns": [
                {
                    "pattern": "llm-platform",
                    "project": "LLM Platform",
                    "confidence": 1.0,
                    "source": "manual",
                    "created_at": "2025-02-26T21:30:00",
                    "updated_at": "2025-02-26T21:30:00"
                }
            ],
            "module_patterns": [
                {
                    "pattern": "runtime/memory",
                    "module": "memory",
                    "confidence": 1.0,
                    "source": "manual",
                    "created_at": "2025-02-26T21:30:00",
                    "updated_at": "2025-02-26T21:30:00"
                }
            ],
            "candidate_patterns": [
                {
                    "pattern": "mobile-app",
                    "project": "Mobile App",
                    "module": None,
                    "frequency": 3,
                    "confidence": 0.8,
                    "sample_contents": ["Working on mobile app feature"],
                    "first_seen": "2025-02-26T21:30:00",
                    "last_seen": "2025-02-26T21:30:00"
                }
            ],
            "auto_learning": True,
            "confidence_threshold": 0.8,
            "frequency_threshold": 3,
            "max_candidates": 100,
            "hot_reload": True,
            "version": "1.0",
            "updated_at": "2025-02-26T21:30:00"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            yield Path(f.name)

        Path(f.name).unlink(missing_ok=True)

    def test_load_config_from_file(self, temp_config_file):
        """Test loading configuration from YAML file."""
        manager = ClassificationConfigManager(config_path=temp_config_file)
        config = manager.load_config()

        assert len(config.project_patterns) == 1
        assert config.project_patterns[0].pattern == "llm-platform"
        assert config.project_patterns[0].project == "LLM Platform"

        assert len(config.module_patterns) == 1
        assert config.module_patterns[0].pattern == "runtime/memory"
        assert config.module_patterns[0].module == "memory"

    def test_get_patterns_as_dict(self, temp_config_file):
        """Test getting patterns as dictionaries for classifier."""
        manager = ClassificationConfigManager(config_path=temp_config_file)
        manager.load_config()

        project_patterns = manager.get_project_patterns()
        module_patterns = manager.get_module_patterns()

        assert project_patterns == {"llm-platform": "LLM Platform"}
        assert module_patterns == {"runtime/memory": "memory"}

    def test_add_project_pattern(self, temp_config_file):
        """Test adding new project pattern."""
        manager = ClassificationConfigManager(config_path=temp_config_file)

        manager.add_project_pattern("new-project", "New Project", 0.9)

        config = manager.get_config()
        patterns = {p.pattern: p.project for p in config.project_patterns}
        assert "new-project" in patterns
        assert patterns["new-project"] == "New Project"

    def test_add_candidate_pattern(self, temp_config_file):
        """Test adding candidate pattern for auto-learning."""
        manager = ClassificationConfigManager(config_path=temp_config_file)

        # Learn a new pattern
        manager.add_candidate_pattern(
            pattern="data-pipeline",
            project="Data Pipeline",
            content_sample="Working on data pipeline module"
        )

        config = manager.get_config()

        # Should have original + new candidate
        candidate_patterns = [cp for cp in config.candidate_patterns if cp.pattern == "data-pipeline"]
        assert len(candidate_patterns) == 1
        assert candidate_patterns[0].frequency == 1
        assert candidate_patterns[0].confidence > 0

    def test_promote_candidate_pattern(self, temp_config_file):
        """Test promoting candidate to official pattern."""
        manager = ClassificationConfigManager(config_path=temp_config_file)

        # Add multiple occurrences of same pattern
        for i in range(5):  # Above threshold
            manager.add_candidate_pattern(
                pattern="frequent-project",
                project="Frequent Project",
                content_sample=f"Working on frequent project task {i}"
            )

        # Promote qualifying candidates
        promoted = manager.promote_candidates(frequency_threshold=3)

        assert len(promoted) == 1
        assert promoted[0].pattern == "frequent-project"

        # Should be added to official patterns
        config = manager.get_config()
        project_patterns = [pp for pp in config.project_patterns if pp.pattern == "frequent-project"]
        assert len(project_patterns) == 1
        assert project_patterns[0].source == "learned"

    def test_remove_pattern(self, temp_config_file):
        """Test removing patterns."""
        manager = ClassificationConfigManager(config_path=temp_config_file)

        # Remove existing pattern
        result = manager.remove_project_pattern("llm-platform")
        assert result is True

        config = manager.get_config()
        patterns = {p.pattern for p in config.project_patterns}
        assert "llm-platform" not in patterns

        # Try to remove non-existent pattern
        result = manager.remove_project_pattern("non-existent")
        assert result is False