"""Resolve a collection or a single item into a typed tree.

Type selection is strict: the caller says ``collection`` or ``mod`` and a
mismatch raises ``WrongTargetTypeError`` before any download starts.
"""

from __future__ import annotations

from collections import deque

from ..core.errors import ApiError, InvalidTargetError, WrongTargetTypeError
from ..core.events import Events, NullEvents
from ..core.models import ItemStatus, NodeKind, WorkshopNode
from ..services.steam_api import COLLECTION_FILETYPE, SteamAPI, parse_target_id

MAX_DEPTH = 10


class Resolver:
    def __init__(self, api: SteamAPI) -> None:
        self.api = api

    def resolve(
        self,
        target: str,
        target_type: str,
        events: Events | None = None,
    ) -> WorkshopNode:
        events = events or NullEvents()
        target_id = parse_target_id(target)
        details = self.api.get_details([target_id])
        own = details.get(target_id)
        if own is None or own.result != 1:
            raise InvalidTargetError(f"Предмет/коллекция {target_id} не найдена или недоступна.")

        if target_type == "mod":
            if own.filetype == COLLECTION_FILETYPE:
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
        if own.filetype != COLLECTION_FILETYPE:
            raise WrongTargetTypeError(
                "Это отдельный мод. Переключите режим на «Мод».",
                actual_type="mod",
            )

        root = self._node_from_details(own, NodeKind.COLLECTION)
        root.selectable = True

        seen = {root.id}
        queue: deque[tuple[WorkshopNode, int]] = deque([(root, 0)])
        while queue:
            parent, depth = queue.popleft()
            if depth >= MAX_DEPTH:
                events.log("warning", f"Достигнут лимит вложенности на {parent.id}.")
                continue
            info = self.api.get_collection(parent.id)
            if info.result != 1:
                raise ApiError(f"Не удалось получить коллекцию {parent.id}.")
            children = sorted(info.children, key=lambda child: child.sortorder)
            for child in children:
                if not child.id or child.id in seen:
                    continue
                seen.add(child.id)
                kind = NodeKind.COLLECTION if child.filetype == COLLECTION_FILETYPE else NodeKind.ITEM
                node = WorkshopNode(id=child.id, kind=kind)
                parent.children.append(node)
                if kind is NodeKind.COLLECTION:
                    queue.append((node, depth + 1))

        events.tree_ready(root)

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
