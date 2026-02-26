"""Tests for memory classification configuration management."""

import pytest
from pathlib import Path
import tempfile
import yaml
from unittest.mock import patch
import asyncio

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
                    "source": "manual"
                }
            ],
            "module_patterns": [
                {
                    "pattern": "runtime/memory",
                    "module": "memory",
                    "confidence": 1.0,
                    "source": "manual"
                }
            ],
            "candidate_patterns": [
                {
                    "pattern": "mobile-app",
                    "project": "Mobile App",
                    "frequency": 3,
                    "confidence": 0.8
                }
            ],
            "auto_learning": True,
            "confidence_threshold": 0.8
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

    def test_save_config_to_file(self, temp_config_file):
        """Test saving configuration to YAML file."""
        manager = ClassificationConfigManager(config_path=temp_config_file)
        config = manager.load_config()

        # Add a new pattern
        new_pattern = ProjectPattern(
            pattern="new-project",
            project="New Project",
            confidence=0.9,
            source="learned"
        )
        config.project_patterns.append(new_pattern)

        manager.save_config(config)

        # Reload and verify
        reloaded_config = manager.load_config()
        assert len(reloaded_config.project_patterns) == 2
        assert reloaded_config.project_patterns[1].pattern == "new-project"

    @pytest.mark.asyncio
    async def test_hot_reload(self, temp_config_file):
        """Test hot reload functionality."""
        manager = ClassificationConfigManager(config_path=temp_config_file)

        # Start watching
        await manager.start_watching()

        # Modify config file
        config_data = {
            "project_patterns": [
                {
                    "pattern": "updated-pattern",
                    "project": "Updated Project",
                    "confidence": 1.0,
                    "source": "manual"
                }
            ],
            "module_patterns": [],
            "candidate_patterns": [],
            "auto_learning": True,
            "confidence_threshold": 0.8
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Give file watcher time to detect change
        await asyncio.sleep(0.1)

        # Verify config was reloaded
        config = manager.get_config()
        assert len(config.project_patterns) == 1
        assert config.project_patterns[0].pattern == "updated-pattern"

        await manager.stop_watching()

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