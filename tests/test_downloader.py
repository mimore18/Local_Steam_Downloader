import zipfile
from pathlib import Path

from steam_workshop_dl.app import downloader as downloader_module
from steam_workshop_dl.app.downloader import Downloader
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

    monkeypatch.setattr(downloader_module, "find_steamcmd", lambda _path: Path("/bin/true"))
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
