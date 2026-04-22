from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any


class MemoryServiceBase:
    @staticmethod
    def utcnow() -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC)

    @staticmethod
    def isoformat(value: datetime.datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def parse_optional_datetime(value: Any) -> datetime.datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        return datetime.datetime.fromisoformat(text)

    @staticmethod
    def dump_jsonl(records: list[dict[str, Any]]) -> str:
        return "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records) + "\n"

    @staticmethod
    def sha256_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
