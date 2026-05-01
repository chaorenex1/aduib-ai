from fastapi import APIRouter, Query

from controllers.common.base import api_endpoint
from service.agent.contracts import ToolingPermissionCommand, ToolingSchemaCommand
from service.agent.tooling_service import AgentToolingService

router = APIRouter(tags=["agent"])


@router.get("/agents/v1/tooling/schema")
@api_endpoint()
async def get_tooling_schema(
    agent_id: int | None = Query(default=None, ge=1),
    mode: str = Query(default="agent"),
    surface: str = Query(default="web"),
):
    return await AgentToolingService.get_schema(ToolingSchemaCommand(agent_id=agent_id, mode=mode, surface=surface))


@router.get("/agents/v1/tooling/permission")
@api_endpoint()
async def get_tooling_permission(
    agent_id: int | None = Query(default=None, ge=1),
    mode: str = Query(default="agent"),
    surface: str = Query(default="web"),
):
    return await AgentToolingService.get_permission(
        ToolingPermissionCommand(agent_id=agent_id, mode=mode, surface=surface)
    )
