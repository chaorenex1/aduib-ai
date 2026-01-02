import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class TaskGradeConfig(BaseSettings):
    grade_model_list: dict[str, Any] = Field(default_factory=dict)
    grade_benchmark_list: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("grade_model_list",mode="before")
    def validate_model_list(cls, values):
        path = Path(__file__).resolve().parent / "task_grade_model_list.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []


    @field_validator("grade_benchmark_list",mode="before")
    def validate_benchmark_list(cls, values):
        path = Path(__file__).resolve().parent / "task_grade_benchmark.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []
