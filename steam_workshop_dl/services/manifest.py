"""Resume manifest stored next to downloaded items."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.models import ItemStatus, WorkshopNode

SCHEMA = 1
MANIFEST_NAME = ".workshop-manifest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Manifest:
    path: Path
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, output_dir: Path) -> "Manifest":
        path = output_dir / MANIFEST_NAME
        if not path.exists():
            return cls(path=path, data={"schema": SCHEMA, "items": {}})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("items"), dict):
                raise ValueError("invalid manifest structure")
        except (OSError, ValueError, json.JSONDecodeError):
            broken = path.with_name(f"{path.name}.broken-{int(datetime.now().timestamp())}")
            try:
                path.replace(broken)
            except OSError:
                pass
            return cls(path=path, data={"schema": SCHEMA, "items": {}})
        raw.setdefault("schema", SCHEMA)
        return cls(path=path, data=raw)

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("items", {})

    def should_skip(
        self,
        node: WorkshopNode,
        *,
        resume: bool = True,
        force: bool = False,
    ) -> bool:
        if force or not resume:
            return False
        entry = self.items.get(node.id)
        if not entry or entry.get("status") != ItemStatus.DONE.value:
            return False
        relative = entry.get("path")
        if not relative:
            return False
        if not (self.path.parent / relative).exists():
            return False
        if node.time_updated is not None and entry.get("time_updated") != node.time_updated:
            return False
        return True

    def mark(
        self,
        node: WorkshopNode,
        relative_path: str,
        *,
        status: ItemStatus = ItemStatus.DONE,
    ) -> None:
        self.items[node.id] = {
            "title": node.title,
            "appid": node.appid,
            "size": node.size,
            "time_updated": node.time_updated,
            "status": status.value,
            "path": Path(relative_path).as_posix(),
            "downloaded_at": _now(),
        }
        self.save()

    def set_target(self, target_id: str, target_type: str) -> None:
        self.data["target_id"] = target_id
        self.data["target_type"] = target_type

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["schema"] = SCHEMA
        self.data["updated_at"] = _now()
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
