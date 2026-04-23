from __future__ import annotations

import base64

from component.storage.base_storage import StorageSnapshot, StorageSnapshotItem, StorageSnapshotRoot


def serialize_snapshot(snapshot: StorageSnapshot) -> dict:
    return {
        "roots": [{"path": root.path, "kind": root.kind} for root in snapshot.roots],
        "items": [
            {
                "path": item.path,
                "data_base64": base64.b64encode(item.data).decode("ascii"),
            }
            for item in snapshot.items
        ],
    }


def deserialize_snapshot(payload: dict) -> StorageSnapshot:
    return StorageSnapshot(
        roots=tuple(StorageSnapshotRoot(path=item["path"], kind=item["kind"]) for item in payload.get("roots") or []),
        items=tuple(
            StorageSnapshotItem(
                path=item["path"],
                data=base64.b64decode(item["data_base64"].encode("ascii")),
            )
            for item in payload.get("items") or []
        ),
    )
