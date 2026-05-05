"""Project CRUD and import endpoints for programmer memory."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from controllers.common.base import api_endpoint
from controllers.memory.schemas import (
    ProjectCreateRequest,
    ProjectImportRequest,
    ProjectListQuery,
    ProjectRecentRequest,
    ProjectUpdateRequest,
)
from libs.deps import CurrentUserDep
from service.memory import MemoryWriteTaskService, ProjectService
from service.memory.base.mappers import (
    project_create_request_to_command,
    project_import_request_to_task_command,
    project_update_request_to_command,
    project_view_to_response,
    recent_project_id_to_response,
)
from service.memory.base.project_contracts import ProjectListQuery as ProjectListServiceQuery

router = APIRouter(prefix="/memories/projects", tags=["Programmer Memory"])


@router.get("/recent")
@api_endpoint()
async def get_recent_project(current_user: CurrentUserDep):
    project_id = ProjectService.get_recent_project_id(user_id=str(current_user["user_id"]))
    return recent_project_id_to_response(project_id)


@router.put("/recent")
@api_endpoint()
async def set_recent_project(payload: ProjectRecentRequest, current_user: CurrentUserDep):
    project_id = ProjectService.set_recent_project_id(
        user_id=str(current_user["user_id"]),
        project_id=payload.projectId,
    )
    return recent_project_id_to_response(project_id)


@router.get("")
@api_endpoint()
async def list_projects(query: Annotated[ProjectListQuery, Depends()], current_user: CurrentUserDep):
    view_list = ProjectService.list_projects(
        user_id=str(current_user["user_id"]),
        query=ProjectListServiceQuery(search=query.search, mode=query.mode),
    )
    return [project_view_to_response(view) for view in view_list]


@router.post("", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreateRequest, current_user: CurrentUserDep):
    command = project_create_request_to_command(payload)
    view = ProjectService.create_project(user_id=str(current_user["user_id"]), command=command)
    return project_view_to_response(view)


@router.post("/{project_id}", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def import_project_materials(project_id: str, payload: ProjectImportRequest):
    """Create or update a project root and import project materials."""

    command = project_import_request_to_task_command(project_id=project_id, payload=payload)
    return await MemoryWriteTaskService.accept_task_request(command)


@router.get("/{project_id}")
@api_endpoint()
async def get_project(project_id: str, current_user: CurrentUserDep):
    """Fetch one frontend-facing project resource."""
    view = ProjectService.get_project(user_id=str(current_user["user_id"]), project_id=project_id)
    return project_view_to_response(view) if view else None


@router.patch("/{project_id}")
@api_endpoint()
async def update_project(project_id: str, payload: ProjectUpdateRequest, current_user: CurrentUserDep):
    command = project_update_request_to_command(payload)
    view = ProjectService.update_project(
        user_id=str(current_user["user_id"]),
        project_id=project_id,
        command=command,
    )
    return project_view_to_response(view)


@router.delete("/{project_id}")
@api_endpoint()
async def delete_project(project_id: str, current_user: CurrentUserDep):
    ProjectService.delete_project(user_id=str(current_user["user_id"]), project_id=project_id)
    return {"deleted": True}
