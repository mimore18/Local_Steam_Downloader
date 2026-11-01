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
import re

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
        "status_downloading_percent": "Downloading: {percent}%",
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
        "threads": "Download threads:",
        "threads_hint": (
            "1 — one SteamCMD batch; 2–16 — parallel, one SteamCMD process "
            "per thread. For large collections 8–12 threads with the dynamic "
            "queue are usually fastest."
        ),
        "threads_each_mod": "One per mod",
        "unstable": "Unstable mode",
        "unstable_hint": (
            "Adds “one SteamCMD per mod” to the thread selector. "
            "Usually slower and may overload Steam or the PC."
        ),
        "dynamic_queue": "Dynamic work queue",
        "dynamic_queue_hint": (
            "Keeps one SteamCMD per thread and gives it the next mod as soon "
            "as it finishes, instead of pre-splitting the list. Recommended."
        ),
        "resume": "Resume incomplete downloads",
        "validate": "Validate files after download",
        "zip": "Pack each mod into a ZIP",
        "language": "Interface language:",
        "theme": "Theme:",
        "theme_light": "Light",
        "theme_dark": "Dark",
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
        "status_downloading_percent": "Скачивание: {percent}%",
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
        "threads": "Потоков загрузки:",
        "threads_hint": (
            "1 — один запуск SteamCMD; 2–16 — параллельно, по одному процессу "
            "SteamCMD на поток. На больших коллекциях обычно быстрее всего "
            "8–12 потоков с динамической очередью."
        ),
        "threads_each_mod": "Каждый мод отдельно",
        "unstable": "Нестабильный режим",
        "unstable_hint": (
            "Добавляет в выбор потоков режим «каждый мод в своём SteamCMD». "
            "Обычно медленнее и может перегрузить Steam или компьютер."
        ),
        "dynamic_queue": "Динамическая очередь",
        "dynamic_queue_hint": (
            "Держит один SteamCMD на поток и выдаёт следующий мод сразу после "
            "завершения предыдущего, без заранее нарезанных списков. "
            "Рекомендуется."
        ),
        "resume": "Докачивать недокачанное (resume)",
        "validate": "Проверять файлы после загрузки (validate)",
        "zip": "Упаковывать каждый мод в ZIP",
        "language": "Язык интерфейса:",
        "theme": "Тема:",
        "theme_light": "Светлая",
        "theme_dark": "Тёмная",
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


# The core and services raise ready-made Russian diagnostics.  The GUI cannot
# change their language without a large refactor, so known messages are mapped
# here at the display boundary.  New messages simply stay as-is until added.
_EN_EXACT: dict[str, str] = {
    "Steam API вернул неожиданный JSON": "Steam API returned unexpected JSON",
    "Steam API не вернул данные коллекции": (
        "Steam API did not return collection data"
    ),
    "Steam API не вернул детали предметов": (
        "Steam API did not return item details"
    ),
    "SteamCMD не найден. Укажите --steamcmd или переменную STEAMCMD_PATH.": (
        "SteamCMD not found. Specify --steamcmd or the STEAMCMD_PATH variable."
    ),
    "SteamCMD не найден. Установите его вручную, укажите --steamcmd "
    "или включите автоматическую загрузку.": (
        "SteamCMD not found. Install it manually, specify --steamcmd, "
        "or enable automatic download."
    ),
    "Для входа под аккаунтом нужен username.": (
        "An account login requires a username."
    ),
    "Истекло время ожидания входа в Steam.": "Steam login timed out.",
    "Ввод кода Steam Guard отменён.": "Steam Guard code entry was canceled.",
    "Ввод пароля отменён.": "Password entry was canceled.",
    "SteamCMD не подтвердил вход. Проверьте логин/пароль/Guard.": (
        "SteamCMD did not confirm the login. "
        "Check the login, password and Guard code."
    ),
    "SteamCMD: анонимный вход и проверка обновлений…": (
        "SteamCMD: anonymous login and update check…"
    ),
    "SteamCMD: вход выполнен.": "SteamCMD: logged in.",
    "SteamCMD: вход выполнен, сессия закэширована.": (
        "SteamCMD: logged in, session cached."
    ),
    "SteamCMD: распаковка архива…": "SteamCMD: extracting the archive…",
    "уже скачано": "already downloaded",
    "нет папки после SteamCMD": "no folder after SteamCMD",
    "отменено": "canceled",
}

_EN_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"Не удалось извлечь ID из ссылки\. Ожидается "
            r"\.\.\.filedetails/\?id=123 или 123\."
        ),
        "Could not extract an ID from the link. "
        "Expected ...filedetails/?id=123 or 123.",
    ),
    (
        re.compile(r"Предмет/коллекция (?P<id>\S+) не найдена или недоступна\."),
        "Item/collection {id} was not found or is unavailable.",
    ),
    (
        re.compile(r"Достигнут лимит вложенности на (?P<id>.+?)\."),
        "Nesting limit reached at {id}.",
    ),
    (
        re.compile(r"Вложенная коллекция (?P<id>\S+) недоступна: (?P<error>.+)"),
        "Nested collection {id} is unavailable: {error}",
    ),
    (
        re.compile(
            r"Элемент (?P<id>\S+) помечен как коллекция, но ею не является\."
        ),
        "Item {id} is marked as a collection but is not one.",
    ),
    (
        re.compile(r"SteamCMD не запустился: (?P<error>.+)"),
        "SteamCMD failed to start: {error}",
    ),
    (
        re.compile(r"Steam API вернул HTTP (?P<code>\d+)"),
        "Steam API returned HTTP {code}",
    ),
    (
        re.compile(r"Steam API недоступен: (?P<error>.+)"),
        "Steam API is unavailable: {error}",
    ),
    (
        re.compile(
            r"Повтор для (?P<count>\d+) предметов "
            r"\(попытка (?P<attempt>\d+)\)\."
        ),
        "Retrying {count} items (attempt {attempt}).",
    ),
    (
        re.compile(r"Не удалось скачать SteamCMD: (?P<error>.+)"),
        "Failed to download SteamCMD: {error}",
    ),
    (
        re.compile(r"Архив SteamCMD содержит небезопасный путь: (?P<name>.+)"),
        "SteamCMD archive contains an unsafe path: {name}",
    ),
    (
        re.compile(
            r"Архив SteamCMD распакован, но (?P<name>\S+) "
            r"не найден в (?P<folder>.+?)\."
        ),
        "SteamCMD archive was extracted, but {name} "
        "was not found in {folder}.",
    ),
    (
        re.compile(
            r"Указанный SteamCMD не найден: (?P<path>.+?)\. "
            r"Исправьте --steamcmd или уберите его, "
            r"чтобы скачать автоматически\."
        ),
        "The specified SteamCMD was not found: {path}. "
        "Fix --steamcmd or leave it empty to download automatically.",
    ),
    (
        re.compile(r"Анонимный вход не удался: (?P<tail>.+)"),
        "Anonymous login failed: {tail}",
    ),
    (
        re.compile(r"SteamCMD закрыл stdin: (?P<error>.+)"),
        "SteamCMD closed stdin: {error}",
    ),
    (
        re.compile(r"SteamCMD: вход под аккаунтом (?P<username>.+?)…"),
        "SteamCMD: logging in as {username}…",
    ),
    (
        re.compile(r"SteamCMD: используется (?P<path>.+)"),
        "SteamCMD: using {path}",
    ),
    (
        re.compile(r"SteamCMD не найден\. Скачивание: (?P<url>.+)"),
        "SteamCMD not found. Downloading: {url}",
    ),
    (
        re.compile(r"SteamCMD будет установлен в: (?P<folder>.+)"),
        "SteamCMD will be installed to: {folder}",
    ),
    (
        re.compile(r"SteamCMD готов: (?P<path>.+)"),
        "SteamCMD ready: {path}",
    ),
]


def translate_message(language: str | None, message: str) -> str:
    """Translate a ready-made service diagnostic when English is selected."""

    # Internal log entries may pass a translation key instead of a message.
    if message in MESSAGES[DEFAULT_LANGUAGE]:
        return translate(language, message)
    if normalize_language(language) != "en":
        return message
    text = message.strip()
    exact = _EN_EXACT.get(text)
    if exact is not None:
        return exact
    for pattern, template in _EN_RULES:
        match = pattern.fullmatch(text)
        if match is None:
            continue
        values = {
            key: translate_message("en", value)
            for key, value in match.groupdict().items()
        }
        return template.format(**values)
    return message

