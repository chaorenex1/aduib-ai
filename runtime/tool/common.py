from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from configs import config


class WorkspaceToolError(ValueError):
    """Raised when a workspace tool request is invalid or unsafe."""


def parse_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def parse_int(value: Any, *, default: int | None) -> int | None:
    if value is None or value == "":
        return default
    return int(value)


def get_workdir() -> Path:
    app_home = config.APP_HOME
    if app_home:
        base_dir = Path(app_home)
    else:
        base_dir = Path.home() / f".{config.APP_NAME.lower()}"
    workdir = (base_dir / "workdir").resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def resolve_workdir_path(path_value: str, *, allow_missing: bool = False) -> tuple[Path, Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        raise WorkspaceToolError("path must be a non-empty string")

    workdir = get_workdir()
    raw_path = Path(path_value.strip())
    resolved = (raw_path if raw_path.is_absolute() else workdir / raw_path).resolve(strict=False)
    if not resolved.is_relative_to(workdir):
        raise WorkspaceToolError("path escapes app.workdir")
    if not allow_missing and not resolved.exists():
        raise WorkspaceToolError(f"path does not exist: {path_value}")
    return workdir, resolved


def relative_to_workdir(path: Path, workdir: Path) -> str:
    rel_path = path.relative_to(workdir).as_posix()
    return rel_path or "."


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars < 1:
        raise WorkspaceToolError("max_chars must be at least 1")
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def is_probably_binary(path: Path) -> bool:
    with path.open("rb") as file_obj:
        chunk = file_obj.read(4096)
    return b"\x00" in chunk


def iter_files(base_path: Path, glob_pattern: str | None = None) -> list[Path]:
    if base_path.is_file():
        if glob_pattern and not fnmatch.fnmatch(base_path.name, glob_pattern):
            return []
        return [base_path]

    candidates = []
    for path in base_path.rglob("*"):
        if not path.is_file():
            continue
        if glob_pattern and not fnmatch.fnmatch(path.name, glob_pattern):
            continue
        candidates.append(path)
    return candidates
