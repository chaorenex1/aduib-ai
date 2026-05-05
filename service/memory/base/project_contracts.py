from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProjectMode = Literal["web", "desktop"]
ProjectStatus = Literal["planning", "active", "done"]
ProjectModeFilter = Literal["web", "desktop", "all"]


class ProjectServiceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectBranchCreateCommand(ProjectServiceSchema):
    name: str = Field(..., min_length=1, max_length=120)
    local_path: str = Field(..., min_length=1, max_length=1000)


class ProjectBranchRecord(ProjectServiceSchema):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=120)
    local_path: str = Field(..., min_length=1, max_length=1000)


class ProjectCreateCommand(ProjectServiceSchema):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    mode: ProjectMode
    status: ProjectStatus = "planning"
    branches: list[ProjectBranchCreateCommand] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode_rules(self) -> ProjectCreateCommand:
        if self.mode == "web" and self.branches:
            raise ValueError("web projects do not support branch path configuration")
        if self.mode == "desktop" and not self.branches:
            raise ValueError("desktop projects require at least one branch path")
        return self


class ProjectUpdateCommand(ProjectServiceSchema):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    status: ProjectStatus | None = None
    branches: list[ProjectBranchRecord] | None = None


class ProjectListQuery(ProjectServiceSchema):
    search: str | None = None
    mode: ProjectModeFilter | None = None


class ProjectView(ProjectServiceSchema):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    mode: ProjectMode
    status: ProjectStatus
    updated_at: str = Field(..., min_length=1)
    branches: list[ProjectBranchRecord] = Field(default_factory=list)
