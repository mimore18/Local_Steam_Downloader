import json
from pathlib import Path

from steam_workshop_dl.core.models import ItemStatus, NodeKind, WorkshopNode
from steam_workshop_dl.services.manifest import Manifest


def make_node(item_id: str = "111", updated: int = 10) -> WorkshopNode:
    return WorkshopNode(
        id=item_id,
        kind=NodeKind.ITEM,
        title="Mod",
        appid=4000,
        time_updated=updated,
    )


def test_mark_and_skip(tmp_path: Path) -> None:
    (tmp_path / "Mod [111]").mkdir()
    manifest = Manifest.load(tmp_path)
    node = make_node()
    manifest.mark(node, "Mod [111]")

    saved = json.loads(manifest.path.read_text(encoding="utf-8"))
    assert saved["schema"] == 1
    assert saved["items"]["111"]["status"] == ItemStatus.DONE.value
    assert manifest.should_skip(node)
    assert not manifest.should_skip(node, force=True)
    assert not manifest.should_skip(node, resume=False)


def test_changed_time_updated_is_not_skipped(tmp_path: Path) -> None:
    (tmp_path / "Mod [111]").mkdir()
    manifest = Manifest.load(tmp_path)
    manifest.mark(make_node(updated=10), "Mod [111]")
    assert manifest.should_skip(make_node(updated=11)) is False


def test_missing_path_is_not_skipped(tmp_path: Path) -> None:
    manifest = Manifest.load(tmp_path)
    manifest.items["111"] = {
        "status": "done",
        "path": "gone",
        "time_updated": 10,
    }
    assert manifest.should_skip(make_node()) is False


def test_broken_manifest_is_renamed(tmp_path: Path) -> None:
    path = tmp_path / ".workshop-manifest.json"
    path.write_text("{broken", encoding="utf-8")
    manifest = Manifest.load(tmp_path)
    assert manifest.items == {}
    assert list(tmp_path.glob(".workshop-manifest.json.broken-*"))
