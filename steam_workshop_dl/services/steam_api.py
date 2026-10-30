"""Minimal client for the public Steam Workshop Web API.

Only two keyless endpoints are used:

* ``GetCollectionDetails`` — resolve collection children;
* ``GetPublishedFileDetails`` — titles, app ids, sizes and availability.

The client is transport-injectable so tests never touch the network.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..core.errors import ApiError, InvalidTargetError

COLLECTION_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
)
DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)
USER_AGENT = "steam-workshop-dl/0.1 (+https://github.com/mimore18/Local_Steam_Downloader)"

TARGET_ID_RE = re.compile(r"[?&]id=(\d+)", re.IGNORECASE)
CHUNK_SIZE = 100

FileType = int
COLLECTION_FILETYPE = 2


@dataclass(frozen=True)
class CollectionChild:
    id: str
    sortorder: int
    filetype: int


@dataclass(frozen=True)
class CollectionInfo:
    id: str
    result: int
    children: list[CollectionChild]


@dataclass(frozen=True)
class FileDetails:
    id: str
    result: int
    title: str
    appid: int | None
    size: int | None
    filetype: int
    time_updated: int | None
    visibility: int | None
    banned: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FileDetails":
        def as_int(value: Any) -> int | None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        return cls(
            id=str(payload.get("publishedfileid", "")),
            result=as_int(payload.get("result")) or 0,
            title=str(payload.get("title") or ""),
            appid=as_int(payload.get("consumer_app_id")),
            size=as_int(payload.get("file_size")),
            filetype=as_int(payload.get("filetype")) or 0,
            time_updated=as_int(payload.get("time_updated")),
            visibility=as_int(payload.get("visibility")),
            banned=bool(as_int(payload.get("banned"))),
        )


def parse_target_id(value: str) -> str:
    """Accept a full Steam URL, ``?id=`` fragment or a bare numeric id."""

    text = value.strip()
    match = TARGET_ID_RE.search(text)
    if match:
        return match.group(1)
    if text.isdigit() and 1 <= len(text) <= 20:
        return text
    raise InvalidTargetError(
        "Не удалось извлечь ID из ссылки. Ожидается ...filedetails/?id=123 или 123."
    )


class SteamAPI:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout = timeout
        self.retries = max(1, retries)
        self._opener = opener
        self._sleep = sleeper

    def _post(self, url: str, pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
        body = urlencode(list(pairs)).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ApiError("Steam API вернул неожиданный JSON")
                return payload
            except HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise ApiError(f"Steam API вернул HTTP {exc.code}") from exc
                last_error = exc
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt + 1 < self.retries:
                self._sleep(2**attempt)
        raise ApiError(f"Steam API недоступен: {last_error}") from last_error

    def get_collection(self, collection_id: str) -> CollectionInfo:
        payload = self._post(
            COLLECTION_URL,
            [("collectioncount", "1"), ("publishedfileids[0]", collection_id)],
        )
        try:
            entry = payload["response"]["collectiondetails"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError("Steam API не вернул данные коллекции") from exc
        children = [
            CollectionChild(
                id=str(child.get("publishedfileid", "")),
                sortorder=int(child.get("sortorder") or 0),
                filetype=int(child.get("filetype") or 0),
            )
            for child in entry.get("children") or []
            if child.get("publishedfileid")
        ]
        return CollectionInfo(
            id=str(entry.get("publishedfileid", collection_id)),
            result=int(entry.get("result") or 0),
            children=children,
        )

    def get_details(self, ids: Iterable[str]) -> dict[str, FileDetails]:
        unique = list(dict.fromkeys(str(item) for item in ids))
        result: dict[str, FileDetails] = {}
        for start in range(0, len(unique), CHUNK_SIZE):
            chunk = unique[start : start + CHUNK_SIZE]
            pairs: list[tuple[str, str]] = [("itemcount", str(len(chunk)))]
            pairs.extend((f"publishedfileids[{index}]", item) for index, item in enumerate(chunk))
            payload = self._post(DETAILS_URL, pairs)
            try:
                details = payload["response"]["publishedfiledetails"]
            except (KeyError, TypeError) as exc:
                raise ApiError("Steam API не вернул детали предметов") from exc
            for item in details or []:
                parsed = FileDetails.from_payload(item)
                if parsed.id:
                    result[parsed.id] = parsed
        return result
