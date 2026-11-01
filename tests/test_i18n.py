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
    translate_message,
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


def test_translate_runtime_messages() -> None:
    assert translate_message(
        "en", "Предмет/коллекция 123 не найдена или недоступна."
    ) == "Item/collection 123 was not found or is unavailable."
    assert translate_message(
        "en", "Steam API вернул HTTP 500"
    ) == "Steam API returned HTTP 500"
    assert translate_message(
        "en",
        "Анонимный вход не удался: ERROR! No subscription",
    ) == "Anonymous login failed: ERROR! No subscription"
    assert translate_message(
        "en",
        "Вложенная коллекция 42 недоступна: Steam API недоступен: timeout",
    ) == (
        "Nested collection 42 is unavailable: "
        "Steam API is unavailable: timeout"
    )
    assert translate_message(
        "en", "SteamCMD: вход выполнен."
    ) == "SteamCMD: logged in."
    # Russian UI keeps the original diagnostic untouched.
    original = "Предмет/коллекция 123 не найдена или недоступна."
    assert translate_message("ru", original) == original
    # Internal log entries may pass a translation key.
    assert translate_message("en", "cancel_requested") == (
        "Cancellation requested…"
    )
    assert translate_message("ru", "ready") == "Готов к работе"
    # Unknown messages are left as-is.
    assert translate_message("en", "custom failure") == "custom failure"


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


def test_gui_theme_switch_and_persistence(app) -> None:
    from steam_workshop_dl.ui.theme import PALETTES

    instance, config_dir = app
    assert instance.theme.get() == "light"

    instance._open_settings()
    dialog = next(
        widget
        for widget in instance.winfo_children()
        if isinstance(widget, tk.Toplevel)
    )
    combos = [
        widget for widget in _walk(dialog) if isinstance(widget, tk.ttk.Combobox)
    ]
    assert len(combos) == 3
    combos[1].set("Тёмная")
    save = next(
        widget
        for widget in _walk(dialog)
        if isinstance(widget, tk.ttk.Button)
        and widget.cget("text") in {"Сохранить", "Save"}
    )
    save.invoke()
    instance.update()

    assert instance.theme.get() == "dark"
    assert instance.log_text.cget("background").lower() == PALETTES["dark"]["field"]
    assert str(instance.github_link.cget("foreground")) == PALETTES["dark"]["link"]

    preferences = config_dir / "steam-workshop-dl" / "gui.json"
    assert '"theme": "dark"' in preferences.read_text(encoding="utf-8")


def test_footer_is_packed_before_the_expanding_split(app) -> None:
    instance, _ = app
    footer = instance.github_link.master
    slaves = instance.pack_slaves()
    assert footer.pack_info()["side"] == "bottom"
    assert slaves.index(footer) < slaves.index(instance.split)
    assert isinstance(instance.split, tk.ttk.Panedwindow)


def test_window_icon_is_loaded(app) -> None:
    instance, _ = app
    assert instance._window_icon.width() == 512


def test_gui_progress_tracks_item_percent(app) -> None:
    from steam_workshop_dl.core.models import ItemStatus

    instance, _ = app
    instance._download_total = 2
    instance._download_done = 0
    instance._item_progress.clear()

    instance._dispatch(("item_progress", "1", 40.0))
    assert float(instance.progress.cget("value")) == 40.0
    assert instance.status.get() == "Скачивание: 20%"

    instance._dispatch(("status", "1", ItemStatus.DONE))
    instance._dispatch(("progress", 1, 2))
    instance._dispatch(("item_progress", "2", 50.0))

    assert float(instance.progress.cget("value")) == 150.0
    assert instance.status.get() == "Скачивание: 75%"


def test_gui_threads_and_unstable_settings(app) -> None:
    import json

    instance, config_dir = app
    assert instance.download_threads.get() == 1
    assert instance.unstable.get() is False

    instance._open_settings()
    dialog = next(
        widget
        for widget in instance.winfo_children()
        if isinstance(widget, tk.Toplevel)
    )
    combos = [
        widget for widget in _walk(dialog) if isinstance(widget, tk.ttk.Combobox)
    ]
    threads_combo = combos[2]
    assert list(threads_combo.cget("values")) == ["1", "2", "3", "4"]

    unstable = next(
        widget
        for widget in _walk(dialog)
        if isinstance(widget, tk.ttk.Checkbutton)
        and widget.cget("text") == "Нестабильный режим"
    )
    unstable.invoke()
    assert "Каждый мод отдельно" in list(threads_combo.cget("values"))

    threads_combo.set("Каждый мод отдельно")
    save = next(
        widget
        for widget in _walk(dialog)
        if isinstance(widget, tk.ttk.Button)
        and widget.cget("text") in {"Сохранить", "Save"}
    )
    save.invoke()
    instance.update()

    assert instance.download_threads.get() == 0
    assert instance.unstable.get() is True
    settings = instance._settings()
    assert settings.download_threads == 0
    assert settings.unstable is True

    preferences = config_dir / "steam-workshop-dl" / "gui.json"
    data = json.loads(preferences.read_text(encoding="utf-8"))
    assert data["download_threads"] == 0
    assert data["unstable"] is True


def test_gui_dynamic_queue_default_and_persistence(app) -> None:
    import json

    instance, config_dir = app
    assert instance.dynamic_queue.get() is True

    instance._open_settings()
    dialog = next(
        widget
        for widget in instance.winfo_children()
        if isinstance(widget, tk.Toplevel)
    )
    dynamic = next(
        widget
        for widget in _walk(dialog)
        if isinstance(widget, tk.ttk.Checkbutton)
        and widget.cget("text") == "Динамическая очередь"
    )
    dynamic.invoke()
    save = next(
        widget
        for widget in _walk(dialog)
        if isinstance(widget, tk.ttk.Button)
        and widget.cget("text") in {"Сохранить", "Save"}
    )
    save.invoke()
    instance.update()

    assert instance.dynamic_queue.get() is False
    assert instance._settings().dynamic_queue is False
    preferences = config_dir / "steam-workshop-dl" / "gui.json"
    data = json.loads(preferences.read_text(encoding="utf-8"))
    assert data["dynamic_queue"] is False


def test_gui_remembers_saved_theme(app) -> None:
    import json

    from steam_workshop_dl.ui.gui import App
    from steam_workshop_dl.ui.theme import PALETTES

    _, config_dir = app
    path = config_dir / "steam-workshop-dl" / "gui.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

    second = App()
    second.withdraw()
    try:
        assert second.theme.get() == "dark"
        assert second.log_text.cget("background").lower() == PALETTES["dark"]["field"]
    finally:
        second.destroy()
