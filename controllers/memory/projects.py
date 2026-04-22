"""Project import endpoints for programmer memory."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from controllers.common.base import api_endpoint, not_implemented
from controllers.memory.schemas import ProjectGetQuery, ProjectImportRequest

router = APIRouter(prefix="/memories/projects", tags=["Programmer Memory"])


@router.post("/{project_id}", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def import_project_materials(project_id: str, _payload: ProjectImportRequest):
    """Create or update a project root and import project materials."""

    not_implemented(f"import project materials for {project_id}")


@router.get("/{project_id}")
@api_endpoint()
async def get_project(
    project_id: str,
    _query: Annotated[ProjectGetQuery, Depends()],
):
    """Fetch a project entity already present under the memory tree."""

    not_implemented(f"get project {project_id}")
