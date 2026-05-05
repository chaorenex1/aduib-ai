from __future__ import annotations

from collections.abc import Iterable

from models import MemoryProject, MemoryProjectRecent, get_db
from service.error.base import RepositoryBase

from ..base import MemoryServiceBase
from ..base.project_contracts import ProjectBranchRecord, ProjectListQuery, ProjectView


class MemoryProjectRepository(RepositoryBase):
    @classmethod
    def list_projects(cls, *, user_id: str, query: ProjectListQuery) -> list[ProjectView]:
        with get_db() as session:
            db_query = session.query(MemoryProject).filter(
                MemoryProject.user_id == user_id,
                MemoryProject.deleted_at.is_(None),
            )
            if query.mode and query.mode != "all":
                db_query = db_query.filter(MemoryProject.mode == query.mode)
            rows = db_query.all()

        projects = [cls._to_view(row) for row in rows]
        filtered = [project for project in projects if cls._matches_query(project, query)]
        return sorted(filtered, key=lambda item: item.updated_at, reverse=True)

    @classmethod
    def get_project(cls, *, user_id: str, project_id: str) -> ProjectView | None:
        with get_db() as session:
            row = (
                session.query(MemoryProject)
                .filter(
                    MemoryProject.user_id == user_id,
                    MemoryProject.project_id == project_id,
                    MemoryProject.deleted_at.is_(None),
                )
                .first()
            )
            return cls._to_view(row) if row else None

    @classmethod
    def create_project(
        cls,
        *,
        user_id: str,
        project_id: str,
        name: str,
        description: str,
        mode: str,
        status: str,
        branches: list[ProjectBranchRecord],
    ) -> ProjectView:
        now = MemoryServiceBase.utcnow()
        with get_db() as session:
            row = MemoryProject(
                project_id=project_id,
                user_id=user_id,
                name=name,
                description=description,
                mode=mode,
                status=status,
                branches_json=[cls._branch_to_payload(branch) for branch in branches],
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            row = cls.commit_and_refresh(session, row)
            return cls._to_view(row)

    @classmethod
    def update_project(
        cls,
        *,
        user_id: str,
        project_id: str,
        name: str | None,
        description: str | None,
        status: str | None,
        branches: list[ProjectBranchRecord] | None,
    ) -> ProjectView:
        with get_db() as session:
            row = (
                session.query(MemoryProject)
                .filter(
                    MemoryProject.user_id == user_id,
                    MemoryProject.project_id == project_id,
                    MemoryProject.deleted_at.is_(None),
                )
                .first()
            )
            if row is None:
                raise LookupError("project not found")

            if name is not None:
                row.name = name
            if description is not None:
                row.description = description
            if status is not None:
                row.status = status
            if branches is not None:
                row.branches_json = [cls._branch_to_payload(branch) for branch in branches]
            row.updated_at = MemoryServiceBase.utcnow()
            row = cls.commit_and_refresh(session, row)
            return cls._to_view(row)

    @classmethod
    def delete_project(cls, *, user_id: str, project_id: str) -> None:
        with get_db() as session:
            row = (
                session.query(MemoryProject)
                .filter(
                    MemoryProject.user_id == user_id,
                    MemoryProject.project_id == project_id,
                    MemoryProject.deleted_at.is_(None),
                )
                .first()
            )
            if row is None:
                return

            row.deleted_at = MemoryServiceBase.utcnow()
            row.updated_at = MemoryServiceBase.utcnow()
            session.commit()

    @classmethod
    def get_recent_project_id(cls, *, user_id: str) -> str | None:
        with get_db() as session:
            row = session.query(MemoryProjectRecent).filter(MemoryProjectRecent.user_id == user_id).first()
            if row is None:
                return None
            return str(row.recent_project_id or "").strip() or None

    @classmethod
    def set_recent_project_id(cls, *, user_id: str, project_id: str | None) -> str | None:
        with get_db() as session:
            row = session.query(MemoryProjectRecent).filter(MemoryProjectRecent.user_id == user_id).first()
            if not project_id:
                if row is not None:
                    session.delete(row)
                    session.commit()
                return None

            now = MemoryServiceBase.utcnow()
            if row is None:
                row = MemoryProjectRecent(
                    user_id=user_id,
                    recent_project_id=project_id,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.recent_project_id = project_id
                row.updated_at = now
            session.commit()
            return project_id

    @staticmethod
    def _matches_query(project: ProjectView, query: ProjectListQuery) -> bool:
        if not query.search:
            return True

        needle = query.search.strip().lower()
        if not needle:
            return True

        branch_text = " ".join(f"{branch.name} {branch.local_path}" for branch in project.branches)
        haystack = f"{project.name} {project.description} {project.mode} {branch_text}".lower()
        return needle in haystack

    @staticmethod
    def _normalize_branches(branches: Iterable[dict]) -> list[ProjectBranchRecord]:
        normalized: list[ProjectBranchRecord] = []
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            normalized.append(
                ProjectBranchRecord(
                    id=str(branch.get("id") or "").strip(),
                    name=str(branch.get("name") or "").strip(),
                    local_path=str(branch.get("local_path") or branch.get("localPath") or "").strip(),
                )
            )
        return normalized

    @staticmethod
    def _branch_to_payload(branch: ProjectBranchRecord) -> dict[str, str]:
        return {
            "id": branch.id,
            "name": branch.name,
            "local_path": branch.local_path,
        }

    @classmethod
    def _to_view(cls, row: MemoryProject) -> ProjectView:
        return ProjectView(
            id=row.project_id,
            name=row.name,
            description=row.description or "",
            mode=row.mode,
            status=row.status,
            updated_at=MemoryServiceBase.isoformat(row.updated_at) or "",
            branches=cls._normalize_branches(row.branches_json or []),
        )
