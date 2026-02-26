"""Memory classification configuration management system."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
from datetime import datetime
import yaml
import re
from pydantic import BaseModel, Field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


logger = logging.getLogger(__name__)


class ProjectPattern(BaseModel):
    """Project name matching pattern configuration."""

    pattern: str = Field(..., description="Pattern to match in content (lowercase)")
    project: str = Field(..., description="Project name to assign")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Pattern confidence score")
    source: str = Field(default="manual", description="Pattern source: manual/learned")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)


class ModulePattern(BaseModel):
    """Module name matching pattern configuration."""

    pattern: str = Field(..., description="Pattern to match in content (lowercase)")
    module: str = Field(..., description="Module name to assign")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Pattern confidence score")
    source: str = Field(default="manual", description="Pattern source: manual/learned")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)


class CandidatePattern(BaseModel):
    """Candidate pattern for auto-learning."""

    pattern: str = Field(..., description="Candidate pattern")
    project: Optional[str] = Field(None, description="Suggested project name")
    module: Optional[str] = Field(None, description="Suggested module name")
    frequency: int = Field(default=1, description="Number of times seen")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Learned confidence")
    sample_contents: List[str] = Field(default_factory=list, description="Sample content that matched")
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)


class ClassificationConfig(BaseModel):
    """Complete classification configuration."""

    project_patterns: List[ProjectPattern] = Field(default_factory=list)
    module_patterns: List[ModulePattern] = Field(default_factory=list)
    candidate_patterns: List[CandidatePattern] = Field(default_factory=list)

    # Auto-learning settings
    auto_learning: bool = Field(default=True, description="Enable auto-learning of patterns")
    confidence_threshold: float = Field(default=0.8, description="Min confidence for auto-promotion")
    frequency_threshold: int = Field(default=3, description="Min frequency for auto-promotion")
    max_candidates: int = Field(default=100, description="Max candidate patterns to keep")

    # Hot-reload settings
    hot_reload: bool = Field(default=True, description="Enable hot-reload of config")

    version: str = Field(default="1.0", description="Configuration version")
    updated_at: datetime = Field(default_factory=datetime.now)


class ConfigFileWatcher(FileSystemEventHandler):
    """File system watcher for configuration hot-reload."""

    def __init__(self, config_manager: ClassificationConfigManager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        if Path(event.src_path).resolve() == self.config_manager.config_path.resolve():
            self.logger.info(f"Configuration file modified: {event.src_path}")
            try:
                asyncio.create_task(self.config_manager._reload_config())
            except RuntimeError:
                # Handle case when no event loop is running
                self.config_manager._sync_reload_config()


class ClassificationConfigManager:
    """Manages classification configuration with hot-reload and auto-learning."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("configs/memory/classification.yaml")
        self._config: Optional[ClassificationConfig] = None
        self._observer: Optional[Observer] = None
        self._watcher: Optional[ConfigFileWatcher] = None
        self.logger = logging.getLogger(__name__)

    def load_config(self) -> ClassificationConfig:
        """Load configuration from file."""
        if not self.config_path.exists():
            self.logger.info(f"Configuration file not found: {self.config_path}")
            self._config = ClassificationConfig()
            self.save_config(self._config)
            return self._config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Handle empty file
            if not data:
                self._config = ClassificationConfig()
            else:
                self._config = ClassificationConfig(**data)

            self.logger.info(f"Loaded configuration from {self.config_path}")
            return self._config

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self._config = ClassificationConfig()
            return self._config

    def save_config(self, config: ClassificationConfig) -> None:
        """Save configuration to file."""
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Update timestamp
            config.updated_at = datetime.now()

            # Convert to dict and save
            data = config.model_dump(mode='python')
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            self._config = config
            self.logger.info(f"Saved configuration to {self.config_path}")

        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise

    def get_config(self) -> ClassificationConfig:
        """Get current configuration."""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    async def start_watching(self) -> None:
        """Start file watching for hot-reload."""
        if not self.get_config().hot_reload:
            return

        if self._observer is not None:
            return  # Already watching

        self._watcher = ConfigFileWatcher(self)
        self._observer = Observer()
        self._observer.schedule(
            self._watcher,
            str(self.config_path.parent),
            recursive=False
        )
        self._observer.start()
        self.logger.info(f"Started watching configuration file: {self.config_path}")

    async def stop_watching(self) -> None:
        """Stop file watching."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._watcher = None
            self.logger.info("Stopped configuration file watching")

    async def _reload_config(self) -> None:
        """Reload configuration asynchronously."""
        # Add small delay to avoid multiple rapid reloads
        await asyncio.sleep(0.1)
        self.load_config()
        self.logger.info("Configuration reloaded")

    def _sync_reload_config(self) -> None:
        """Reload configuration synchronously."""
        self.load_config()
        self.logger.info("Configuration reloaded (sync)")

    def add_candidate_pattern(
        self,
        pattern: str,
        project: Optional[str] = None,
        module: Optional[str] = None,
        content_sample: Optional[str] = None
    ) -> None:
        """Add or update a candidate pattern for auto-learning."""
        config = self.get_config()

        if not config.auto_learning:
            return

        # Normalize pattern
        pattern = pattern.lower().strip()

        # Find existing candidate
        existing = None
        for candidate in config.candidate_patterns:
            if candidate.pattern == pattern:
                existing = candidate
                break

        if existing:
            # Update existing candidate
            existing.frequency += 1
            existing.last_seen = datetime.now()
            if project:
                existing.project = project
            if module:
                existing.module = module
            if content_sample and len(existing.sample_contents) < 5:
                existing.sample_contents.append(content_sample[:200])  # Limit length
        else:
            # Create new candidate
            candidate = CandidatePattern(
                pattern=pattern,
                project=project,
                module=module,
                frequency=1,
                confidence=self._calculate_initial_confidence(pattern, content_sample),
                sample_contents=[content_sample[:200]] if content_sample else []
            )
            config.candidate_patterns.append(candidate)

        # Cleanup old candidates if too many
        if len(config.candidate_patterns) > config.max_candidates:
            # Sort by frequency * confidence and keep top ones
            config.candidate_patterns.sort(
                key=lambda c: c.frequency * c.confidence,
                reverse=True
            )
            config.candidate_patterns = config.candidate_patterns[:config.max_candidates]

        self.save_config(config)

    def promote_candidates(self, frequency_threshold: Optional[int] = None) -> List[ProjectPattern]:
        """Promote qualifying candidates to official patterns."""
        config = self.get_config()
        threshold = frequency_threshold or config.frequency_threshold

        promoted = []
        remaining_candidates = []

        for candidate in config.candidate_patterns:
            should_promote = (
                candidate.frequency >= threshold and
                candidate.confidence >= config.confidence_threshold
            )

            if should_promote and candidate.project:
                # Create official pattern
                pattern = ProjectPattern(
                    pattern=candidate.pattern,
                    project=candidate.project,
                    confidence=candidate.confidence,
                    source="learned"
                )
                config.project_patterns.append(pattern)
                promoted.append(pattern)

                self.logger.info(f"Promoted candidate pattern: {candidate.pattern} -> {candidate.project}")
            elif should_promote and candidate.module:
                # Create module pattern
                module_pattern = ModulePattern(
                    pattern=candidate.pattern,
                    module=candidate.module,
                    confidence=candidate.confidence,
                    source="learned"
                )
                config.module_patterns.append(module_pattern)

                self.logger.info(f"Promoted candidate module: {candidate.pattern} -> {candidate.module}")
            else:
                remaining_candidates.append(candidate)

        config.candidate_patterns = remaining_candidates

        if promoted:
            self.save_config(config)

        return promoted

    def _calculate_initial_confidence(self, pattern: str, content_sample: Optional[str]) -> float:
        """Calculate initial confidence for a candidate pattern."""
        confidence = 0.5  # Base confidence

        # Increase confidence for specific patterns
        if len(pattern) > 3:
            confidence += 0.1

        if '-' in pattern or '/' in pattern:  # Structured names
            confidence += 0.1

        if content_sample:
            # Increase confidence if pattern appears in meaningful context
            context_indicators = ['project', 'module', 'service', 'api', 'system']
            content_lower = content_sample.lower()
            for indicator in context_indicators:
                if indicator in content_lower:
                    confidence += 0.05

        return min(confidence, 1.0)

    def get_project_patterns(self) -> Dict[str, str]:
        """Get project patterns as dict for MemoryClassifier."""
        config = self.get_config()
        return {p.pattern: p.project for p in config.project_patterns}

    def get_module_patterns(self) -> Dict[str, str]:
        """Get module patterns as dict for MemoryClassifier."""
        config = self.get_config()
        return {p.pattern: p.module for p in config.module_patterns}

    def add_project_pattern(self, pattern: str, project: str, confidence: float = 1.0) -> None:
        """Add a new project pattern."""
        config = self.get_config()

        # Check if pattern already exists
        for existing in config.project_patterns:
            if existing.pattern == pattern.lower():
                existing.project = project
                existing.confidence = confidence
                existing.updated_at = datetime.now()
                self.save_config(config)
                return

        # Add new pattern
        new_pattern = ProjectPattern(
            pattern=pattern.lower(),
            project=project,
            confidence=confidence
        )
        config.project_patterns.append(new_pattern)
        self.save_config(config)

    def add_module_pattern(self, pattern: str, module: str, confidence: float = 1.0) -> None:
        """Add a new module pattern."""
        config = self.get_config()

        # Check if pattern already exists
        for existing in config.module_patterns:
            if existing.pattern == pattern.lower():
                existing.module = module
                existing.confidence = confidence
                existing.updated_at = datetime.now()
                self.save_config(config)
                return

        # Add new pattern
        new_pattern = ModulePattern(
            pattern=pattern.lower(),
            module=module,
            confidence=confidence
        )
        config.module_patterns.append(new_pattern)
        self.save_config(config)

    def remove_project_pattern(self, pattern: str) -> bool:
        """Remove a project pattern."""
        config = self.get_config()

        for i, existing in enumerate(config.project_patterns):
            if existing.pattern == pattern.lower():
                del config.project_patterns[i]
                self.save_config(config)
                return True

        return False

    def remove_module_pattern(self, pattern: str) -> bool:
        """Remove a module pattern."""
        config = self.get_config()

        for i, existing in enumerate(config.module_patterns):
            if existing.pattern == pattern.lower():
                del config.module_patterns[i]
                self.save_config(config)
                return True

        return False


# Rebuild models to resolve forward references after all classes are defined
ProjectPattern.model_rebuild()
ModulePattern.model_rebuild()
CandidatePattern.model_rebuild()
ClassificationConfig.model_rebuild()