import zipfile
from pathlib import Path
from threading import Barrier, Event

from steam_workshop_dl.app import downloader as downloader_module
from steam_workshop_dl.app.downloader import Downloader
from steam_workshop_dl.core.events import NullEvents
from steam_workshop_dl.core.models import ItemStatus, NodeKind, Settings, WorkshopNode


def make_node(item_id: str = "111", title: str = "Some Mod") -> WorkshopNode:
    return WorkshopNode(id=item_id, kind=NodeKind.ITEM, title=title, appid=4000, size=10)


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "steam-content"
    source.mkdir()
    (source / "file.txt").write_text("data", encoding="utf-8")
    (source / "sub").mkdir()
    (source / "sub" / "nested.txt").write_text("nested", encoding="utf-8")
    return source


def test_install_copies_folder(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "out"
    settings = Settings(output_dir=output)
    relative = Downloader()._install(make_node(), source, settings)
    assert relative == Path("Some Mod [111]")
    assert (output / relative / "file.txt").read_text(encoding="utf-8") == "data"


def test_install_zip(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "out"
    settings = Settings(output_dir=output, zip_items=True)
    relative = Downloader()._install(make_node(), source, settings)
    assert relative == Path("Some Mod [111].zip")
    with zipfile.ZipFile(output / relative) as archive:
        assert "file.txt" in archive.namelist()
        assert "sub/nested.txt" in archive.namelist()


def test_install_by_app(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "out"
    settings = Settings(output_dir=output, by_app=True)
    relative = Downloader()._install(make_node(), source, settings)
    assert relative == Path("4000") / "Some Mod [111]"
    assert (output / relative / "file.txt").exists()


def test_run_respects_explicit_items(monkeypatch, tmp_path: Path) -> None:
    """GUI retry passes a subset; the downloader must not fall back to selection."""

    first = make_node("111", "First")
    second = make_node("222", "Second")
    root = WorkshopNode(id="1", kind=NodeKind.COLLECTION, title="Collection")
    root.children = [first, second]

    monkeypatch.setattr(downloader_module, "ensure_steamcmd", lambda _settings, _events: Path("/bin/true"))
    monkeypatch.setattr(downloader_module, "ensure_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        Downloader,
        "_download_pass",
        lambda self, steamcmd, items, settings, events, cancel: {
            item.id: tmp_path / "source" for item in items
        },
    )
    monkeypatch.setattr(
        Downloader, "_install", lambda self, node, source, settings: Path("x")
    )

    summary = Downloader().run(
        Settings(output_dir=tmp_path / "out"), root=root, items=[second]
    )

    assert summary.done == 1
    assert second.status is ItemStatus.DONE
    assert first.status is ItemStatus.PENDING


class Recorder(NullEvents):
    def __init__(self) -> None:
        self.statuses: list[tuple[str, ItemStatus]] = []
        self.progress: list[tuple[str, float]] = []

    def item_status(self, item_id: str, status: ItemStatus, detail: str = "") -> None:
        self.statuses.append((item_id, status))

    def item_progress(self, item_id: str, percent: float) -> None:
        self.progress.append((item_id, percent))


def test_handle_line_marks_only_current_item() -> None:
    first = make_node("111", "First")
    second = make_node("222", "Second")
    found: dict[str, Path | None] = {"111": None, "222": None}
    state: dict[str, object] = {"current": None, "percent": {}}
    events = Recorder()

    Downloader._handle_line(
        "Downloading item 111 ...", found, {"111": first, "222": second}, state, events
    )
    Downloader._handle_line(
        "Update state (0x61) downloading, progress: 42.50",
        found,
        {"111": first, "222": second},
        state,
        events,
    )

    assert first.status is ItemStatus.DOWNLOADING
    assert second.status is ItemStatus.PENDING
    assert events.statuses == [("111", ItemStatus.DOWNLOADING)]
    assert events.progress == [("111", 0.0), ("111", 42.5)]


def test_handle_line_ignores_progress_between_items() -> None:
    node = make_node("111", "First")
    found: dict[str, Path | None] = {"111": None}
    state: dict[str, object] = {"current": None, "percent": {}}
    events = Recorder()

    Downloader._handle_line(
        "Update state (0x61) downloading, progress: 42.50",
        found,
        {"111": node},
        state,
        events,
    )

    assert events.progress == []
    assert node.status is ItemStatus.PENDING


def test_worker_count_modes() -> None:
    assert Downloader._worker_count(Settings(download_threads=1), 5) == 1
    assert Downloader._worker_count(Settings(download_threads=3), 5) == 3
    assert Downloader._worker_count(Settings(download_threads=4), 2) == 2
    assert (
        Downloader._worker_count(
            Settings(download_threads=0, unstable=True), 7
        )
        == 7
    )
    assert Downloader._worker_count(Settings(download_threads=0), 7) == 1


def test_download_parallel_runs_workers_concurrently(monkeypatch) -> None:
    nodes = [make_node("111", "First"), make_node("222", "Second")]
    barrier = Barrier(2)

    def fake_single(self, steamcmd, node, settings, events, cancel):
        barrier.wait(timeout=5)
        return None

    monkeypatch.setattr(Downloader, "_download_single", fake_single)
    found = Downloader()._download_parallel(
        Path("/bin/true"),
        nodes,
        Settings(download_threads=2),
        NullEvents(),
        Event(),
        2,
    )

    assert found == {"111": None, "222": None}
