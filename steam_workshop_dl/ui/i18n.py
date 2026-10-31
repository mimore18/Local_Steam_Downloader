"""Minimal runtime translations for the GUI (English/Russian).

The language defaults to the primary language reported by the operating
system.  Users can override it in the settings dialog; the choice is stored
in a small JSON file next to the regular config.

Only user-facing UI strings live here.  Diagnostics coming from the core and
SteamCMD keep their original wording.
"""

from __future__ import annotations

import locale
import os

from collections.abc import Mapping

DEFAULT_LANGUAGE = "en"
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
}

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "ready": "Ready",
        "list_not_loaded": "No list loaded",
        "type": "Type:",
        "collection": "Collection",
        "mod": "Mod",
        "target": "Link/ID:",
        "output": "Download folder:",
        "choose_output": "Choose folder…",
        "load_list": "Load mod list",
        "download_selected": "Download selected mods",
        "retry_failed": "Retry failed",
        "stop": "Stop download",
        "select_all": "Select all",
        "select_none": "Clear selection",
        "settings": "Settings…",
        "mod_list": "Mod list",
        "totals": "{selected} of {available} selected · {size}",
        "column_name": "Name",
        "column_size": "Size",
        "column_status": "Status",
        "log": "Log",
        "status_choose": "Choose a type and click “Load mod list”",
        "status_loading_list": "Loading list…",
        "status_list_loaded": "List loaded",
        "status_downloading": "Downloading: {count} mod(s)…",
        "status_wrong_type": "Different target type",
        "status_done": "Done",
        "status_finished_errors": "Finished with errors",
        "status_error": "Error",
        "cancel_requested": "Cancellation requested…",
        "no_link_title": "No link",
        "no_link_text": "Paste a link or ID.",
        "login_required_title": "Login required",
        "login_required_text": "Enter your Steam login to use an account.",
        "empty_title": "Nothing selected",
        "empty_text": "No mods are selected.",
        "nothing_retry_title": "Nothing to retry",
        "nothing_retry_text": "There are no failed or canceled downloads.",
        "wrong_title": "Wrong target type",
        "wrong_text": "This is a {label}. Switch the mode and try again?",
        "label_collection": "collection",
        "label_mod": "mod",
        "error_title": "Error",
        "finished_title": "Download finished",
        "finished_text": "{summary}\nTime: {elapsed} s",
        "summary_done": "downloaded: {count}",
        "summary_skipped": "skipped: {count}",
        "summary_failed": "errors: {count}",
        "summary_unavailable": "unavailable: {count}",
        "summary_canceled": "canceled: {count}",
        "unexpected_error": "Unexpected error: {error}",
        "prompt_title": "Steam login",
        "prompt_password": "Steam password for “{username}”:",
        "guard_title": "Steam Guard",
        "guard_code": "Steam Guard code:",
        "folder_unavailable": "Folder unavailable",
        "settings_title": "Settings",
        "interface": "Interface",
        "choose_steamcmd_title": "Select the SteamCMD executable",
        "steamcmd": "SteamCMD",
        "steamcmd_path": "SteamCMD path:",
        "choose_file": "Choose file…",
        "bootstrap": "Download SteamCMD automatically if it is missing",
        "bootstrap_hint": (
            "If the path is empty, SteamCMD will be found or downloaded "
            "automatically."
        ),
        "auth": "Steam authorization",
        "anonymous": "Anonymous",
        "account": "Steam account",
        "username": "Login:",
        "auth_hint": "The password and Steam Guard code will be requested during download.",
        "options": "Download options",
        "resume": "Resume incomplete downloads",
        "validate": "Validate files after download",
        "zip": "Pack each mod into a ZIP",
        "language": "Interface language:",
        "save": "Save",
        "cancel": "Cancel",
        "status_pending": "Pending",
        "status_downloading_item": "Downloading…",
        "status_done_item": "Done",
        "status_skipped": "Skipped",
        "status_failed": "Error",
        "status_unavailable": "Unavailable",
        "status_canceled": "Canceled",
        "item_placeholder": "item {id}",
    },
    "ru": {
        "ready": "Готов к работе",
        "list_not_loaded": "Список не загружен",
        "type": "Тип:",
        "collection": "Коллекция",
        "mod": "Мод",
        "target": "Ссылка/ID:",
        "output": "Папка загрузки:",
        "choose_output": "Выбрать папку…",
        "load_list": "Загрузить список модов",
        "download_selected": "Скачать выбранные моды",
        "retry_failed": "Повторить неудачные",
        "stop": "Остановить загрузку",
        "select_all": "Выделить все",
        "select_none": "Снять выделение",
        "settings": "Настройки…",
        "mod_list": "Список модов",
        "totals": "Выбрано {selected} из {available} · {size}",
        "column_name": "Название",
        "column_size": "Размер",
        "column_status": "Статус",
        "log": "Лог",
        "status_choose": "Выберите тип и нажмите «Загрузить список модов»",
        "status_loading_list": "Получение списка…",
        "status_list_loaded": "Список загружен",
        "status_downloading": "Загрузка: {count} мод(ов)…",
        "status_wrong_type": "Другой тип цели",
        "status_done": "Готово",
        "status_finished_errors": "Завершено с ошибками",
        "status_error": "Ошибка",
        "cancel_requested": "Запрошена отмена…",
        "no_link_title": "Нет ссылки",
        "no_link_text": "Вставьте ссылку или ID.",
        "login_required_title": "Нужен логин",
        "login_required_text": "Для входа под аккаунтом укажите логин Steam.",
        "empty_title": "Пусто",
        "empty_text": "Не выбрано ни одного мода.",
        "nothing_retry_title": "Нечего повторять",
        "nothing_retry_text": "Ошибок и отменённых загрузок нет.",
        "wrong_title": "Похоже, выбран другой тип",
        "wrong_text": "Это {label}. Переключить режим и повторить?",
        "label_collection": "коллекция",
        "label_mod": "мод",
        "error_title": "Ошибка",
        "finished_title": "Загрузка завершена",
        "finished_text": "{summary}\nВремя: {elapsed} с",
        "summary_done": "скачано: {count}",
        "summary_skipped": "пропущено: {count}",
        "summary_failed": "ошибок: {count}",
        "summary_unavailable": "недоступно: {count}",
        "summary_canceled": "отменено: {count}",
        "unexpected_error": "Неожиданная ошибка: {error}",
        "prompt_title": "Вход в Steam",
        "prompt_password": "Пароль Steam для «{username}»:",
        "guard_title": "Steam Guard",
        "guard_code": "Код Steam Guard:",
        "folder_unavailable": "Папка недоступна",
        "settings_title": "Настройки",
        "interface": "Интерфейс",
        "choose_steamcmd_title": "Выберите исполняемый файл SteamCMD",
        "steamcmd": "SteamCMD",
        "steamcmd_path": "Путь к SteamCMD:",
        "choose_file": "Указать файл…",
        "bootstrap": "Скачивать SteamCMD автоматически, если он не найден",
        "bootstrap_hint": (
            "Если путь пуст, SteamCMD будет найден или скачан автоматически."
        ),
        "auth": "Авторизация Steam",
        "anonymous": "Анонимно",
        "account": "Аккаунт Steam",
        "username": "Логин:",
        "auth_hint": "Пароль и код Steam Guard будут запрошены при загрузке.",
        "options": "Параметры загрузки",
        "resume": "Докачивать недокачанное (resume)",
        "validate": "Проверять файлы после загрузки (validate)",
        "zip": "Упаковывать каждый мод в ZIP",
        "language": "Язык интерфейса:",
        "save": "Сохранить",
        "cancel": "Отмена",
        "status_pending": "Ожидает",
        "status_downloading_item": "Скачивается…",
        "status_done_item": "Готово",
        "status_skipped": "Пропущено",
        "status_failed": "Ошибка",
        "status_unavailable": "Недоступен",
        "status_canceled": "Отменено",
        "item_placeholder": "элемент {id}",
    },
}


def normalize_language(value: str | None) -> str | None:
    """Return a supported language code for *value*, or ``None``."""

    if not value:
        return None
    cleaned = value.strip().lower()
    for separator in (":", ";"):
        cleaned = cleaned.split(separator, 1)[0]
    cleaned = cleaned.split(".", 1)[0].split("@", 1)[0]
    base = cleaned.replace("-", "_").split("_", 1)[0]
    return base if base in LANGUAGE_NAMES else None


def _windows_ui_language() -> str | None:
    """Primary Windows UI language, mapped to a supported code."""

    if os.name != "nt":
        return None
    try:
        import ctypes

        lang_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
    except Exception:  # pragma: no cover - only reachable on Windows
        return None
    # LANGID low 10 bits are the primary language; 0x19 is Russian.
    return "ru" if (lang_id & 0x3FF) == 0x19 else "en"


def system_language() -> str:
    """Detect the OS primary language, falling back to English."""

    windows = _windows_ui_language()
    if windows:
        return windows

    candidates: list[str] = []
    for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(name, "")
        if not value:
            continue
        if name == "LANGUAGE":
            candidates.extend(value.split(":"))
        else:
            candidates.append(value)

    try:
        detected = locale.getlocale()[0]
    except (ValueError, TypeError):  # pragma: no cover - platform specific
        detected = None
    if detected:
        candidates.append(detected)

    for candidate in candidates:
        code = normalize_language(candidate)
        if code:
            return code
    return DEFAULT_LANGUAGE


def translate(language: str | None, key: str, /, **values: object) -> str:
    """Translate *key* for *language* and interpolate *values*."""

    code = normalize_language(language) or DEFAULT_LANGUAGE
    table: Mapping[str, str] = MESSAGES.get(code, MESSAGES[DEFAULT_LANGUAGE])
    template = table.get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LANGUAGE].get(key, key)
    return template.format(**values) if values else template
