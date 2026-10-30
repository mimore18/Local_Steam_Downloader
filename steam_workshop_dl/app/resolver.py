"""Resolve a collection or a single item into a typed tree.

Type selection is strict: the caller says ``collection`` or ``mod`` and a
mismatch raises ``WrongTargetTypeError`` before any download starts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..core.errors import ApiError, InvalidTargetError, WrongTargetTypeError
from ..core.events import Events, NullEvents
from ..core.models import ItemStatus, NodeKind, WorkshopNode
from ..services.steam_api import (
    COLLECTION_FILETYPE,
    CollectionInfo,
    SteamAPI,
    parse_target_id,
)

MAX_DEPTH = 10


class Resolver:
    def __init__(self, api: SteamAPI) -> None:
        self.api = api

    def resolve(
        self,
        target: str,
        target_type: str,
        events: Events | None = None,
        *,
        workers: int = 4,
    ) -> WorkshopNode:
        events = events or NullEvents()
        target_id = parse_target_id(target)
        details = self.api.get_details([target_id])
        own = details.get(target_id)
        if own is None or own.result != 1:
            raise InvalidTargetError(f"Предмет/коллекция {target_id} не найдена или недоступна.")

        # ``GetPublishedFileDetails`` reports filetype=0 even for many real
        # collections, so the only reliable test is ``GetCollectionDetails``:
        # result 1 means collection, result 9 means a single item.
        collection_info = self.api.get_collection(target_id)
        is_collection = collection_info.result == 1

        if target_type == "mod":
            if is_collection:
                raise WrongTargetTypeError(
                    "Это коллекция. Переключите режим на «Коллекция».",
                    actual_type="collection",
                )
            node = self._node_from_details(own, NodeKind.ITEM)
            node.selectable = True
            events.tree_ready(node)
            events.metadata_updated(node)
            return node

        if target_type != "collection":
            raise ValueError(f"unknown target type: {target_type!r}")
        if not is_collection:
            raise WrongTargetTypeError(
                "Это отдельный мод. Переключите режим на «Мод».",
                actual_type="mod",
            )

        root = self._node_from_details(own, NodeKind.COLLECTION)
        root.selectable = True

        seen = {root.id}
        frontier: list[tuple[WorkshopNode, int, CollectionInfo | None]] = [
            (root, 0, collection_info)
        ]
        first_level = True

        def fetch(entry: tuple[WorkshopNode, int, CollectionInfo | None]):
            node, _depth, preloaded = entry
            if preloaded is not None:
                return preloaded, None
            try:
                return self.api.get_collection(node.id), None
            except ApiError as exc:
                return None, exc

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            while frontier:
                active = [entry for entry in frontier if entry[1] < MAX_DEPTH]
                for node, depth, _preloaded in frontier:
                    if depth >= MAX_DEPTH:
                        events.log(
                            "warning",
                            f"Достигнут лимит вложенности на {node.id}.",
                        )

                next_frontier: list[
                    tuple[WorkshopNode, int, CollectionInfo | None]
                ] = []
                if active:
                    results = list(pool.map(fetch, active))
                    for (parent, depth, _preloaded), (info, error) in zip(
                        active, results
                    ):
                        if error is not None:
                            events.log(
                                "warning",
                                f"Вложенная коллекция {parent.id} недоступна: {error}",
                            )
                            self._mark_unavailable(parent)
                            continue
                        if info is None or info.result != 1:
                            events.log(
                                "warning",
                                f"Элемент {parent.id} помечен как коллекция, "
                                "но ею не является.",
                            )
                            self._mark_unavailable(parent)
                            continue
                        children = sorted(
                            info.children, key=lambda child: child.sortorder
                        )
                        for child in children:
                            if not child.id or child.id in seen:
                                continue
                            seen.add(child.id)
                            kind = (
                                NodeKind.COLLECTION
                                if child.filetype == COLLECTION_FILETYPE
                                else NodeKind.ITEM
                            )
                            node = WorkshopNode(id=child.id, kind=kind)
                            parent.children.append(node)
                            if kind is NodeKind.COLLECTION:
                                next_frontier.append((node, depth + 1, None))

                frontier = next_frontier
                if first_level:
                    events.tree_ready(root)
                    first_level = False
                else:
                    events.tree_updated(root)

        all_nodes = list(root.walk())
        all_details = self.api.get_details(node.id for node in all_nodes)
        for node in all_nodes:
            info = all_details.get(node.id)
            if info is None:
                node.selectable = False
                node.selected = False
                node.status = ItemStatus.UNAVAILABLE
                continue
            node.title = info.title
            node.appid = info.appid
            node.size = info.size
            node.time_updated = info.time_updated
            node.visibility = info.visibility
            node.banned = info.banned
            if node.kind is NodeKind.ITEM:
                available = info.result == 1 and not info.banned
                node.selectable = available
                node.selected = available
                if not available:
                    node.status = ItemStatus.UNAVAILABLE

        events.metadata_updated(root)
        return root

    @staticmethod
    def _mark_unavailable(node: WorkshopNode) -> None:
        node.kind = NodeKind.ITEM
        node.selectable = False
        node.selected = False
        node.status = ItemStatus.UNAVAILABLE

    @staticmethod
    def _node_from_details(details, kind: NodeKind) -> WorkshopNode:
        return WorkshopNode(
            id=details.id,
            kind=kind,
            title=details.title,
            appid=details.appid,
            size=details.size,
            time_updated=details.time_updated,
            visibility=details.visibility,
            banned=details.banned,
        )
