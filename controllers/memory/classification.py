"""Memory classification configuration REST API controller."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from runtime.memory.classification import (
    ClassificationConfig,
    ClassificationConfigManager,
    ProjectPattern,
    ModulePattern,
    CandidatePattern,
)


# Initialize router and config manager
router = APIRouter(prefix="/api/memory/classification", tags=["Memory Classification"])

# Global config manager instance
_config_manager: Optional[ClassificationConfigManager] = None


def get_config_manager() -> ClassificationConfigManager:
    """Get or create the configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ClassificationConfigManager()
    return _config_manager


# Request/Response models
class ProjectPatternRequest(BaseModel):
    """Request model for creating/updating project patterns."""
    pattern: str = Field(..., description="Pattern to match (case-insensitive)")
    project: str = Field(..., description="Project name to assign")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


class ModulePatternRequest(BaseModel):
    """Request model for creating/updating module patterns."""
    pattern: str = Field(..., description="Pattern to match (case-insensitive)")
    module: str = Field(..., description="Module name to assign")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration settings."""
    auto_learning: Optional[bool] = Field(None, description="Enable/disable auto-learning")
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Min confidence for promotion")
    frequency_threshold: Optional[int] = Field(None, ge=1, description="Min frequency for promotion")
    max_candidates: Optional[int] = Field(None, ge=1, description="Max candidates to keep")
    hot_reload: Optional[bool] = Field(None, description="Enable/disable hot reload")


class PromotionRequest(BaseModel):
    """Request model for promoting candidates."""
    frequency_threshold: Optional[int] = Field(None, ge=1, description="Override frequency threshold")


class ClassificationResponse(BaseModel):
    """Response model for full configuration."""
    config: ClassificationConfig
    stats: Dict[str, Any]


# API Endpoints
@router.get("/config", response_model=ClassificationResponse)
async def get_classification_config(
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Get the current classification configuration."""
    config = config_manager.get_config()

    stats = {
        "project_patterns_count": len(config.project_patterns),
        "module_patterns_count": len(config.module_patterns),
        "candidate_patterns_count": len(config.candidate_patterns),
        "auto_learning_enabled": config.auto_learning,
        "last_updated": config.updated_at.isoformat()
    }

    return ClassificationResponse(config=config, stats=stats)


@router.patch("/config")
async def update_classification_config(
    request: ConfigUpdateRequest,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Update configuration settings."""
    config = config_manager.get_config()

    if request.auto_learning is not None:
        config.auto_learning = request.auto_learning
    if request.confidence_threshold is not None:
        config.confidence_threshold = request.confidence_threshold
    if request.frequency_threshold is not None:
        config.frequency_threshold = request.frequency_threshold
    if request.max_candidates is not None:
        config.max_candidates = request.max_candidates
    if request.hot_reload is not None:
        config.hot_reload = request.hot_reload

    config_manager.save_config(config)

    return {"message": "Configuration updated successfully"}


@router.get("/patterns/projects", response_model=List[ProjectPattern])
async def get_project_patterns(
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Get all project patterns."""
    config = config_manager.get_config()
    return config.project_patterns


@router.post("/patterns/projects")
async def add_project_pattern(
    request: ProjectPatternRequest,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Add or update a project pattern."""
    config_manager.add_project_pattern(
        pattern=request.pattern,
        project=request.project,
        confidence=request.confidence
    )

    return {"message": f"Project pattern '{request.pattern}' -> '{request.project}' added successfully"}


@router.delete("/patterns/projects/{pattern}")
async def remove_project_pattern(
    pattern: str,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Remove a project pattern."""
    success = config_manager.remove_project_pattern(pattern)

    if not success:
        raise HTTPException(status_code=404, detail=f"Project pattern '{pattern}' not found")

    return {"message": f"Project pattern '{pattern}' removed successfully"}


@router.get("/patterns/modules", response_model=List[ModulePattern])
async def get_module_patterns(
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Get all module patterns."""
    config = config_manager.get_config()
    return config.module_patterns


@router.post("/patterns/modules")
async def add_module_pattern(
    request: ModulePatternRequest,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Add or update a module pattern."""
    config_manager.add_module_pattern(
        pattern=request.pattern,
        module=request.module,
        confidence=request.confidence
    )

    return {"message": f"Module pattern '{request.pattern}' -> '{request.module}' added successfully"}


@router.delete("/patterns/modules/{pattern}")
async def remove_module_pattern(
    pattern: str,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Remove a module pattern."""
    success = config_manager.remove_module_pattern(pattern)

    if not success:
        raise HTTPException(status_code=404, detail=f"Module pattern '{pattern}' not found")

    return {"message": f"Module pattern '{pattern}' removed successfully"}


@router.get("/candidates", response_model=List[CandidatePattern])
async def get_candidate_patterns(
    limit: int = Query(default=50, ge=1, le=200, description="Max candidates to return"),
    min_frequency: int = Query(default=1, ge=1, description="Minimum frequency filter"),
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Get candidate patterns for review."""
    config = config_manager.get_config()

    # Filter and sort candidates
    candidates = [
        candidate for candidate in config.candidate_patterns
        if candidate.frequency >= min_frequency
    ]

    # Sort by frequency * confidence (descending)
    candidates.sort(key=lambda c: c.frequency * c.confidence, reverse=True)

    return candidates[:limit]


@router.post("/candidates/promote")
async def promote_candidates(
    request: PromotionRequest,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Promote qualifying candidate patterns to official patterns."""
    promoted = config_manager.promote_candidates(
        frequency_threshold=request.frequency_threshold
    )

    return {
        "message": f"Promoted {len(promoted)} candidate patterns",
        "promoted": [{"pattern": p.pattern, "project": p.project} for p in promoted]
    }


@router.delete("/candidates/{pattern}")
async def remove_candidate_pattern(
    pattern: str,
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Remove a specific candidate pattern."""
    config = config_manager.get_config()

    # Find and remove the candidate
    for i, candidate in enumerate(config.candidate_patterns):
        if candidate.pattern == pattern.lower():
            del config.candidate_patterns[i]
            config_manager.save_config(config)
            return {"message": f"Candidate pattern '{pattern}' removed successfully"}

    raise HTTPException(status_code=404, detail=f"Candidate pattern '{pattern}' not found")


@router.post("/reload")
async def reload_configuration(
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Reload configuration from file."""
    config_manager.load_config()
    return {"message": "Configuration reloaded from file"}


@router.get("/stats")
async def get_classification_stats(
    config_manager: ClassificationConfigManager = Depends(get_config_manager)
):
    """Get classification statistics and insights."""
    config = config_manager.get_config()

    # Calculate stats
    total_patterns = len(config.project_patterns) + len(config.module_patterns)
    total_candidates = len(config.candidate_patterns)

    # Top candidates by frequency
    top_candidates = sorted(
        config.candidate_patterns,
        key=lambda c: c.frequency,
        reverse=True
    )[:5]

    # Promotion ready candidates
    promotion_ready = [
        candidate for candidate in config.candidate_patterns
        if (candidate.frequency >= config.frequency_threshold and
            candidate.confidence >= config.confidence_threshold)
    ]

    return {
        "total_patterns": total_patterns,
        "project_patterns": len(config.project_patterns),
        "module_patterns": len(config.module_patterns),
        "total_candidates": total_candidates,
        "promotion_ready": len(promotion_ready),
        "auto_learning_enabled": config.auto_learning,
        "top_candidates": [
            {
                "pattern": c.pattern,
                "frequency": c.frequency,
                "confidence": c.confidence,
                "project": c.project,
                "module": c.module
            }
            for c in top_candidates
        ],
        "promotion_ready_list": [
            {
                "pattern": c.pattern,
                "frequency": c.frequency,
                "confidence": c.confidence,
                "project": c.project,
                "module": c.module
            }
            for c in promotion_ready
        ]
    }


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "memory-classification-config"}