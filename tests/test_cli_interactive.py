from __future__ import annotations

from pathlib import Path

import pytest

from steam_workshop_dl.core.models import NodeKind, Summary, WorkshopNode
from steam_workshop_dl.ui import cli


def feed_input(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    iterator = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


def test_ask_type_accepts_numbers_and_words(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_input(monkeypatch, ["2"])
    assert cli._ask_type() == "mod"

    feed_input(monkeypatch, ["коллекция"])
    assert cli._ask_type() == "collection"

    feed_input(monkeypatch, ["ерунда", ""])
    assert cli._ask_type() == "collection"


def test_confirm_defaults_to_no(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_input(monkeypatch, [""])
    assert cli._confirm("Скачать?") is False

    feed_input(monkeypatch, ["да"])
    assert cli._confirm("Скачать?") is True


def test_interactive_wizard_downloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = WorkshopNode(id="123", kind=NodeKind.ITEM, title="Mod", appid=4000, size=1024)
    captured: dict[str, object] = {}

    class FakeResolver:
        def __init__(self, _api: object) -> None:
            pass

        def resolve(self, target: str, target_type: str, events: object):
            captured["target"] = target
            captured["target_type"] = target_type
            return node

    class FakeDownloader:
        def run(self, settings, *, root=None, events=None, **kwargs):
            captured["settings"] = settings
            captured["root"] = root
            return Summary(done=1)

    monkeypatch.setattr(cli, "setup_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "SteamAPI", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "Resolver", FakeResolver)
    monkeypatch.setattr(cli, "Downloader", FakeDownloader)
    feed_input(monkeypatch, ["2", "123", "", "y"])

    code = cli.interactive_main()

    assert code == 0
    assert captured["target"] == "123"
    assert captured["target_type"] == "mod"
    settings = captured["settings"]
    assert settings.auth_mode == "anonymous"
    assert settings.output_dir == Path(cli.default_output_dir()).expanduser()
    assert captured["root"] is node
