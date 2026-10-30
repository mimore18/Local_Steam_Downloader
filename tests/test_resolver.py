import pytest

from steam_workshop_dl.app.resolver import Resolver
from steam_workshop_dl.core.errors import InvalidTargetError, WrongTargetTypeError
from steam_workshop_dl.core.models import ItemStatus, NodeKind
from steam_workshop_dl.services.steam_api import (
    CollectionChild,
    CollectionInfo,
    FileDetails,
)


def details(item_id: str, *, filetype: int = 0, result: int = 1, title: str = "Item",
            appid: int = 4000) -> FileDetails:
    return FileDetails(
        id=item_id,
        result=result,
        title=title,
        appid=appid,
        size=100,
        filetype=filetype,
        time_updated=10,
        visibility=0,
        banned=result != 1,
    )


class FakeAPI:
    def __init__(self) -> None:
        self.details = {
            "100": details("100", filetype=2, title="Root"),
            "1": details("1", title="One"),
            "2": details("2", title="Two"),
            "3": details("3", result=9, title="Gone"),
            "200": details("200", filetype=2, title="Sub"),
        }
        self.collections = {
            "100": CollectionInfo(
                "100",
                1,
                [
                    CollectionChild("1", 0, 0),
                    CollectionChild("200", 1, 2),
                    CollectionChild("3", 2, 0),
                ],
            ),
            "200": CollectionInfo(
                "200",
                1,
                [CollectionChild("2", 0, 0), CollectionChild("1", 1, 0)],
            ),
        }

    def get_details(self, ids):
        return {item_id: self.details[item_id] for item_id in ids if item_id in self.details}

    def get_collection(self, collection_id):
        return self.collections.get(
            collection_id, CollectionInfo(collection_id, 9, [])
        )


def test_resolve_collection_tree() -> None:
    root = Resolver(FakeAPI()).resolve("100", "collection")
    assert root.kind is NodeKind.COLLECTION
    assert root.title == "Root"
    assert [child.id for child in root.children] == ["1", "200", "3"]

    sub = root.children[1]
    assert sub.kind is NodeKind.COLLECTION
    assert [child.id for child in sub.children] == ["2"]  # duplicate 1 removed

    unavailable = root.children[2]
    assert unavailable.selectable is False
    assert unavailable.selected is False

    items = list(root.items())
    assert {item.id for item in items} == {"1", "2", "3"}
    assert next(item for item in items if item.id == "1").title == "One"


def test_resolve_mod_rejects_collection() -> None:
    with pytest.raises(WrongTargetTypeError) as exc:
        Resolver(FakeAPI()).resolve("100", "mod")
    assert exc.value.actual_type == "collection"


def test_resolve_collection_rejects_mod() -> None:
    with pytest.raises(WrongTargetTypeError) as exc:
        Resolver(FakeAPI()).resolve("1", "collection")
    assert exc.value.actual_type == "mod"


def test_resolve_single_mod() -> None:
    root = Resolver(FakeAPI()).resolve("1", "mod")
    assert root.kind is NodeKind.ITEM
    assert root.title == "One"
    assert root.selectable is True


def test_resolve_missing_target() -> None:
    with pytest.raises(InvalidTargetError):
        Resolver(FakeAPI()).resolve("999", "collection")


def test_collection_detected_by_collection_endpoint() -> None:
    """Real API reports filetype=0 for collections; children still resolve."""

    api = FakeAPI()
    api.details["300"] = details("300", filetype=0, title="Modern Collection")
    api.collections["300"] = CollectionInfo(
        "300", 1, [CollectionChild("1", 0, 0)]
    )

    root = Resolver(api).resolve("300", "collection")
    assert root.kind is NodeKind.COLLECTION
    assert [child.id for child in root.children] == ["1"]

    with pytest.raises(WrongTargetTypeError) as exc:
        Resolver(api).resolve("300", "mod")
    assert exc.value.actual_type == "collection"


def test_broken_nested_collection_does_not_abort() -> None:
    api = FakeAPI()
    api.details["300"] = details("300", filetype=0, title="Modern Collection")
    api.collections["300"] = CollectionInfo(
        "300",
        1,
        [CollectionChild("1", 0, 0), CollectionChild("400", 1, 2)],
    )

    root = Resolver(api).resolve("300", "collection")
    broken = next(child for child in root.children if child.id == "400")
    assert broken.kind is NodeKind.ITEM
    assert broken.selectable is False
    assert broken.status is ItemStatus.UNAVAILABLE
    assert [child.id for child in root.children] == ["1", "400"]


def test_progressive_tree_events() -> None:
    from steam_workshop_dl.core.events import NullEvents

    class Recorder(NullEvents):
        def __init__(self) -> None:
            self.ready = 0
            self.updated = 0

        def tree_ready(self, root):
            self.ready += 1

        def tree_updated(self, root):
            self.updated += 1

    recorder = Recorder()
    Resolver(FakeAPI()).resolve("100", "collection", recorder, workers=1)
    assert recorder.ready == 1
    assert recorder.updated >= 1
