from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from service.memory.base.contracts import PlannerToolRequest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_planner_tool_executor_rejects_unsupported_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        PlannerToolRequest.model_validate({"tool": "search", "args": {}})
