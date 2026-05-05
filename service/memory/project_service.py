from __future__ import annotations

import uuid

from .base import (
    MemoryProjectNotFoundError,
    MemoryServiceBase,
    ProjectBranchRecord,
    ProjectCreateCommand,
    ProjectListQuery,
    ProjectUpdateCommand,
    ProjectView,
)
from .repository import MemoryProjectRepository


class ProjectService(MemoryServiceBase):
    repository = MemoryProjectRepository

    @classmethod
    def list_projects(cls, *, user_id: str, query: ProjectListQuery) -> list[ProjectView]:
        return cls.repository.list_projects(user_id=user_id, query=query)

    @classmethod
    def get_project(cls, *, user_id: str, project_id: str) -> ProjectView | None:
        return cls.repository.get_project(user_id=user_id, project_id=project_id)

    @classmethod
    def create_project(cls, *, user_id: str, command: ProjectCreateCommand) -> ProjectView:
        project_id = str(uuid.uuid4())
        branches = [
            ProjectBranchRecord(
                id=str(uuid.uuid4()),
                name=branch.name,
                local_path=branch.local_path,
            )
            for branch in command.branches
        ]
        view = cls.repository.create_project(
            user_id=user_id,
            project_id=project_id,
            name=command.name,
            description=command.description,
            mode=command.mode,
            status=command.status,
            branches=branches,
        )
        cls.repository.set_recent_project_id(user_id=user_id, project_id=view.id)
        return view

    @classmethod
    def update_project(cls, *, user_id: str, project_id: str, command: ProjectUpdateCommand) -> ProjectView:
        try:
            return cls.repository.update_project(
                user_id=user_id,
                project_id=project_id,
                name=command.name,
                description=command.description,
                status=command.status,
                branches=command.branches,
            )
        except LookupError as exc:
            raise MemoryProjectNotFoundError("project not found", details={"project_id": project_id}) from exc

    @classmethod
    def delete_project(cls, *, user_id: str, project_id: str) -> None:
        cls.repository.delete_project(user_id=user_id, project_id=project_id)
        if cls.repository.get_recent_project_id(user_id=user_id) == project_id:
            cls.repository.set_recent_project_id(user_id=user_id, project_id=None)

    @classmethod
    def get_recent_project_id(cls, *, user_id: str) -> str | None:
        return cls.repository.get_recent_project_id(user_id=user_id)

    @classmethod
    def set_recent_project_id(cls, *, user_id: str, project_id: str | None) -> str | None:
        if project_id is None:
            return cls.repository.set_recent_project_id(user_id=user_id, project_id=None)

        project = cls.repository.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            raise MemoryProjectNotFoundError("project not found", details={"project_id": project_id})
        return cls.repository.set_recent_project_id(user_id=user_id, project_id=project_id)
