from __future__ import annotations

import tkinter as tk

import pytest

from steam_workshop_dl.core.naming import human_size
from steam_workshop_dl.services.config import (
    load_gui_preferences,
    save_gui_preferences,
)
from steam_workshop_dl.ui.i18n import (
    LANGUAGE_NAMES,
    normalize_language,
    system_language,
    translate,
)


def test_normalize_language() -> None:
    assert normalize_language("ru_RU.UTF-8") == "ru"
    assert normalize_language("en-US") == "en"
    assert normalize_language("ru:en") == "ru"
    assert normalize_language("C") is None
    assert normalize_language("de_DE") is None
    assert normalize_language(None) is None


def test_system_language_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert system_language() == "ru"

    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert system_language() == "en"


def test_translate_known_and_fallback() -> None:
    assert translate("ru", "ready") == "Готов к работе"
    assert translate("en", "ready") == "Ready"
    assert translate("en", "totals", selected=2, available=5, size="1 GB") == (
        "2 of 5 selected · 1 GB"
    )
    # Unknown language and unknown key fall back to English / key.
    assert translate("de", "ready") == "Ready"
    assert translate("en", "does.not.exist") == "does.not.exist"


def test_language_names_cover_translations() -> None:
    assert set(LANGUAGE_NAMES) == {"en", "ru"}


def test_gui_preferences_roundtrip(tmp_path) -> None:
    path = tmp_path / "gui.json"
    assert load_gui_preferences(path) == {}

    save_gui_preferences({"language": "en"}, path)
    save_gui_preferences({"other": 1}, path)
    assert load_gui_preferences(path) == {"language": "en", "other": 1}


def test_human_size_language() -> None:
    assert human_size(2048, language="ru") == "2.0 КБ"
    assert human_size(2048, language="en") == "2.0 KB"
    assert human_size(512) == "512 Б"
    assert human_size(512, language="en") == "512 B"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.delenv("LANGUAGE", raising=False)
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")

    from steam_workshop_dl.ui.gui import App

    try:
        instance = App()
    except tk.TclError as exc:  # pragma: no cover - depends on the environment
        pytest.skip(f"no display: {exc}")
    instance.withdraw()
    yield instance, tmp_path
    instance.destroy()


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def test_gui_language_switch_and_persistence(app) -> None:
    from steam_workshop_dl.core.models import NodeKind, WorkshopNode

    instance, config_dir = app
    assert instance.language.get() == "ru"

    root = WorkshopNode(id="100", kind=NodeKind.COLLECTION, title="Root")
    root.children.append(
        WorkshopNode(id="1", kind=NodeKind.ITEM, title="One", size=2048)
    )
    instance.root_node = root
    instance.tree.populate(root)
    instance._update_totals()
    assert instance.totals.get().endswith("2.0 КБ")
    assert instance.tree.item("1", "values")[1] == "Ожидает"

    instance._open_settings()
    dialog = next(
        widget
        for widget in instance.winfo_children()
        if isinstance(widget, tk.Toplevel)
    )
    combo = next(
        widget for widget in _walk(dialog) if isinstance(widget, tk.ttk.Combobox)
    )
    combo.set("English")
    save = next(
        widget
        for widget in _walk(dialog)
        if isinstance(widget, tk.ttk.Button)
        and widget.cget("text") in {"Сохранить", "Save"}
    )
    save.invoke()
    instance.update()

    assert instance.language.get() == "en"
    assert instance.show_button.cget("text") == "Load mod list"
    assert instance.status.get() == "Ready"
    assert instance.totals.get().endswith("2.0 KB")
    assert instance.tree.heading("#0", "text") == "Name"
    assert instance.tree.item("1", "values")[1] == "Pending"

    preferences = config_dir / "steam-workshop-dl" / "gui.json"
    assert preferences.exists()
    assert '"language": "en"' in preferences.read_text(encoding="utf-8")


def test_gui_remembers_saved_language(app) -> None:
    import json

    from steam_workshop_dl.ui.gui import App

    _, config_dir = app
    path = config_dir / "steam-workshop-dl" / "gui.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"language": "en"}), encoding="utf-8")

    second = App()
    second.withdraw()
    try:
        assert second.language.get() == "en"
        assert second.show_button.cget("text") == "Load mod list"
    finally:
        second.destroy()
