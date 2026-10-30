"""Tkinter GUI.

All network/SteamCMD work runs in a daemon worker; widgets are touched only
from the Tk main thread via a queue.  The GUI intentionally shares the same
core objects as the CLI and contains no download policy of its own.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..app.downloader import Downloader
from ..app.resolver import Resolver
from ..core.errors import WorkshopError, WrongTargetTypeError
from ..core.models import ItemStatus, Settings, Summary, WorkshopNode
from ..core.naming import human_size
from ..core.tree import selected_items
from ..services.steam_api import SteamAPI
from .gui_tree import CheckTree

RETRYABLE = {ItemStatus.FAILED, ItemStatus.CANCELED}


class PromptRequest:
    """A credential request travelling from the worker to the Tk main thread."""

    def __init__(self, kind: str, username: str) -> None:
        self.kind = kind
        self.username = username
        self.value: str | None = None
        self.done = threading.Event()


class GuiPrompter:
    """Prompter implementation backed by modal Tk dialogs."""

    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages

    def _ask(self, kind: str, username: str) -> str | None:
        request = PromptRequest(kind, username)
        self.messages.put(("prompt", request))
        if not request.done.wait(timeout=600):
            return None
        return request.value

    def ask_password(self, username: str) -> str | None:
        return self._ask("password", username)

    def ask_steam_guard(self, username: str) -> str | None:
        return self._ask("guard", username)


class GuiEvents:
    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages

    def log(self, level: str, message: str) -> None:
        self.messages.put(("log", level, message))

    def tree_ready(self, root: WorkshopNode) -> None:
        self.messages.put(("tree", root))

    def metadata_updated(self, root: WorkshopNode) -> None:
        self.messages.put(("refresh",))

    def item_status(self, item_id: str, status: ItemStatus, detail: str = "") -> None:
        self.messages.put(("status", item_id, status, detail))

    def progress(self, done: int, total: int, current_id: str | None) -> None:
        self.messages.put(("progress", done, total))

    def finished(self, summary: Summary) -> None:
        self.messages.put(("finished", summary))


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Steam Workshop Downloader")
        self.geometry("1040x760")
        self.minsize(820, 580)

        self.messages: queue.Queue = queue.Queue()
        self.events = GuiEvents(self.messages)
        self.prompter = GuiPrompter(self.messages)
        self.root_node: WorkshopNode | None = None
        self.worker: threading.Thread | None = None
        self.cancel = threading.Event()
        self._busy_widgets: list[tk.Widget] = []

        self.target = tk.StringVar()
        self.output = tk.StringVar(value=str(Path.home() / "Downloads" / "workshop"))
        self.steamcmd = tk.StringVar()
        self.target_type = tk.StringVar(value="collection")
        self.auth_mode = tk.StringVar(value="anonymous")
        self.username = tk.StringVar()
        self.resume = tk.BooleanVar(value=True)
        self.validate = tk.BooleanVar(value=False)
        self.zip_items = tk.BooleanVar(value=False)
        self.search = tk.StringVar()
        self.status = tk.StringVar(value="Готов к работе")
        self.totals = tk.StringVar(value="Список не загружен")

        self._build()
        self.search.trace_add("write", lambda *_: self._apply_filter())
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Тип:").grid(row=0, column=0, sticky="w")
        types = ttk.Frame(top)
        types.grid(row=0, column=1, columnspan=2, sticky="w", padx=(8, 0))
        self._busy_widgets.append(
            ttk.Radiobutton(
                types, text="Коллекция", value="collection", variable=self.target_type
            )
        )
        self._busy_widgets.append(
            ttk.Radiobutton(types, text="Мод", value="mod", variable=self.target_type)
        )
        for widget in self._busy_widgets[-2:]:
            widget.pack(side="left", padx=(0, 12))

        ttk.Label(top, text="Ссылка/ID:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        target_entry = ttk.Entry(top, textvariable=self.target)
        target_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self._busy_widgets.append(target_entry)

        ttk.Label(top, text="Куда:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        output_entry = ttk.Entry(top, textvariable=self.output)
        output_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        choose_button = ttk.Button(top, text="Выбрать", command=self._choose_output)
        choose_button.grid(row=2, column=2, padx=(8, 0), pady=(8, 0))
        self._busy_widgets.extend([output_entry, choose_button])

        ttk.Label(top, text="SteamCMD:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        steamcmd_entry = ttk.Entry(top, textvariable=self.steamcmd)
        steamcmd_entry.grid(row=3, column=1, sticky="ew", pady=(8, 0))
        steamcmd_button = ttk.Button(
            top, text="Найти…", command=self._choose_steamcmd
        )
        steamcmd_button.grid(row=3, column=2, padx=(8, 0), pady=(8, 0))
        self._busy_widgets.extend([steamcmd_entry, steamcmd_button])
        ttk.Label(
            top,
            text="Оставьте пустым — программа найдёт SteamCMD автоматически.",
            foreground="#666666",
        ).grid(row=4, column=1, columnspan=2, sticky="w")

        auth = ttk.Frame(top)
        auth.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(auth, text="Авторизация:").pack(side="left")
        anon = ttk.Radiobutton(
            auth, text="Анонимно", value="anonymous", variable=self.auth_mode
        )
        anon.pack(side="left", padx=(8, 0))
        login = ttk.Radiobutton(
            auth, text="Аккаунт Steam", value="login", variable=self.auth_mode
        )
        login.pack(side="left", padx=(12, 0))
        ttk.Label(auth, text="Логин:").pack(side="left", padx=(12, 0))
        username_entry = ttk.Entry(auth, textvariable=self.username, width=20)
        username_entry.pack(side="left", padx=(6, 0))
        self._busy_widgets.extend([anon, login, username_entry])
        ttk.Label(
            auth,
            text="пароль и Steam Guard спросит в отдельном окне",
            foreground="#666666",
        ).pack(side="left", padx=(10, 0))

        options = ttk.Frame(top)
        options.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(options, text="Параметры:").pack(side="left")
        for text, variable in (
            ("докачивать (resume)", self.resume),
            ("проверять файлы (validate)", self.validate),
            ("упаковывать в ZIP", self.zip_items),
        ):
            check = ttk.Checkbutton(options, text=text, variable=variable)
            check.pack(side="left", padx=(8, 0))
            self._busy_widgets.append(check)

        actions = ttk.Frame(top)
        actions.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.show_button = ttk.Button(
            actions, text="Показать список", command=self._show_list
        )
        self.show_button.pack(side="left")
        self.download_button = ttk.Button(
            actions, text="Скачать выбранное", command=self._download
        )
        self.download_button.pack(side="left", padx=(8, 0))
        self.retry_button = ttk.Button(
            actions, text="Повторить ошибки", command=self._retry_failed
        )
        self.retry_button.pack(side="left", padx=(8, 0))
        select_all = ttk.Button(
            actions, text="Выбрать все", command=lambda: self.tree.select_all(True)
        )
        select_all.pack(side="left", padx=(8, 0))
        select_none = ttk.Button(
            actions, text="Снять все", command=lambda: self.tree.select_all(False)
        )
        select_none.pack(side="left", padx=(8, 0))
        self.cancel_button = ttk.Button(
            actions, text="Отмена", command=self._cancel, state="disabled"
        )
        self.cancel_button.pack(side="right")
        self._busy_widgets.extend(
            [self.show_button, self.download_button, self.retry_button,
             select_all, select_none]
        )
        top.columnconfigure(1, weight=1)

        tree_frame = ttk.Frame(self, padding=(10, 0, 10, 0))
        tree_frame.pack(fill="both", expand=True)

        search_bar = ttk.Frame(tree_frame)
        search_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(search_bar, text="Поиск:").pack(side="left")
        search_entry = ttk.Entry(search_bar, textvariable=self.search)
        search_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Button(
            search_bar, text="Сбросить", command=lambda: self.search.set("")
        ).pack(side="left", padx=(8, 0))
        ttk.Label(search_bar, textvariable=self.totals).pack(side="right", padx=(12, 0))

        tree_area = ttk.Frame(tree_frame)
        tree_area.pack(fill="both", expand=True)
        self.tree = CheckTree(tree_area, on_change=self._update_totals)
        scrollbar = ttk.Scrollbar(tree_area, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        self.progress = ttk.Progressbar(bottom, length=260, mode="determinate")
        self.progress.pack(side="right")

        log_frame = ttk.LabelFrame(self, text="Лог", padding=6)
        log_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=7, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------------ input
    def _choose_output(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=self.output.get() or str(Path.home())
        )
        if chosen:
            self.output.set(chosen)

    def _choose_steamcmd(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Выберите исполняемый файл SteamCMD",
            initialdir=str(Path.home()),
        )
        if chosen:
            self.steamcmd.set(chosen)

    def _settings(self) -> Settings:
        steamcmd = self.steamcmd.get().strip()
        username = self.username.get().strip()
        return Settings(
            target=self.target.get().strip(),
            target_type=self.target_type.get(),
            output_dir=Path(self.output.get()).expanduser(),
            steamcmd=Path(steamcmd).expanduser() if steamcmd else None,
            auth_mode=self.auth_mode.get(),
            username=username or None,
            resume=self.resume.get(),
            validate=self.validate.get(),
            zip_items=self.zip_items.get(),
        )

    # ------------------------------------------------------------------ actions
    def _show_list(self) -> None:
        if self._busy():
            return
        target = self.target.get().strip()
        if not target:
            messagebox.showwarning("Нет ссылки", "Вставьте ссылку или ID.")
            return
        if self.auth_mode.get() == "login" and not self.username.get().strip():
            messagebox.showwarning(
                "Нужен логин",
                "Для входа под аккаунтом укажите логин Steam.",
            )
            return

        target_type = self.target_type.get()
        self._set_busy(True, "Получение списка…")
        self.cancel.clear()
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)

        def work() -> None:
            try:
                root = Resolver(SteamAPI()).resolve(target, target_type, self.events)
                self.messages.put(("preview_done", root))
            except WrongTargetTypeError as exc:
                self.messages.put(("wrong_type", str(exc), exc.actual_type))
            except WorkshopError as exc:
                self.messages.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self.messages.put(("error", f"Неожиданная ошибка: {exc}"))

        self._start_worker(work)

    def _download(self) -> None:
        if self._busy() or self.root_node is None:
            return
        items = selected_items(self.root_node)
        if not items:
            messagebox.showinfo("Пусто", "Не выбрано ни одного мода.")
            return
        self._start_download(items)

    def _retry_failed(self) -> None:
        if self._busy() or self.root_node is None:
            return
        failed = [
            node
            for node in self.root_node.items()
            if node.status in RETRYABLE and node.selectable
        ]
        if not failed:
            messagebox.showinfo("Нечего повторять", "Ошибок и отменённых загрузок нет.")
            return
        self._start_download(failed)

    def _start_download(self, items: list[WorkshopNode]) -> None:
        root = self.root_node
        if root is None:
            return
        settings = self._settings()
        if settings.auth_mode == "login" and not settings.username:
            messagebox.showwarning(
                "Нужен логин", "Для входа под аккаунтом укажите логин Steam."
            )
            return
        try:
            settings.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Папка недоступна", str(exc))
            return

        self.cancel.clear()
        self._set_busy(True, f"Загрузка: {len(items)} мод(ов)…")
        self.progress.configure(mode="determinate", maximum=max(len(items), 1), value=0)

        def work() -> None:
            try:
                Downloader().run(
                    settings,
                    root=root,
                    items=items,
                    events=self.events,
                    prompter=self.prompter,
                    cancel=self.cancel,
                )
            except WorkshopError as exc:
                self.messages.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001
                self.messages.put(("error", f"Неожиданная ошибка: {exc}"))

        self._start_worker(work)

    def _start_worker(self, work) -> None:
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _cancel(self) -> None:
        self.cancel.set()
        self._log("info", "Запрошена отмена…")
        self.cancel_button.configure(state="disabled")

    # ------------------------------------------------------------------ state
    def _busy(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def _set_busy(self, busy: bool, text: str) -> None:
        self.status.set(text)
        state = "disabled" if busy else "normal"
        for widget in self._busy_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if not busy:
            self.progress.stop()
            self.progress.configure(mode="determinate")

    def _update_totals(self) -> None:
        if self.root_node is None:
            self.totals.set("Список не загружен")
            return
        available, selected = self.root_node.counts()
        size = self.root_node.total_size(selected_only=True)
        self.totals.set(f"Выбрано {selected} из {available} · {human_size(size)}")

    def _apply_filter(self) -> None:
        self.tree.set_filter(self.search.get())

    # ------------------------------------------------------------------ event pump
    def _poll(self) -> None:
        try:
            while True:
                message = self.messages.get_nowait()
                self._dispatch(message)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _dispatch(self, message: tuple) -> None:
        kind = message[0]
        if kind == "log":
            self._log(message[1], message[2])
        elif kind == "tree":
            self.root_node = message[1]
            self.tree.populate(message[1])
            self._update_totals()
        elif kind == "refresh":
            self.tree.refresh()
            self._update_totals()
        elif kind == "status":
            self.tree.update_status(message[1], message[2])
        elif kind == "progress":
            done, total = message[1], message[2]
            self.progress.configure(maximum=max(total, 1), value=done)
        elif kind == "preview_done":
            self.root_node = message[1]
            self.worker = None
            self._update_totals()
            self._set_busy(False, "Список загружен")
        elif kind == "prompt":
            self._handle_prompt(message[1])
        elif kind == "wrong_type":
            self._handle_wrong_type(message[1], message[2])
        elif kind == "finished":
            self._handle_finished(message[1])
        elif kind == "error":
            self.worker = None
            self._set_busy(False, "Ошибка")
            self._log("error", message[1])
            messagebox.showerror("Ошибка", message[1])

    def _handle_prompt(self, request: PromptRequest) -> None:
        try:
            if request.kind == "password":
                request.value = simpledialog.askstring(
                    "Вход в Steam",
                    f"Пароль Steam для «{request.username}»:",
                    show="*",
                    parent=self,
                )
            else:
                request.value = simpledialog.askstring(
                    "Steam Guard",
                    "Код Steam Guard:",
                    parent=self,
                )
        finally:
            request.done.set()

    def _handle_wrong_type(self, message: str, actual_type: str) -> None:
        self.worker = None
        self._set_busy(False, "Другой тип цели")
        label = "коллекция" if actual_type == "collection" else "мод"
        if messagebox.askyesno(
            "Похоже, выбран другой тип",
            f"{message}\n\nЭто {label}. Переключить режим и повторить?",
        ):
            self.target_type.set(actual_type)
            self._show_list()

    def _handle_finished(self, summary: Summary) -> None:
        self.worker = None
        self._set_busy(False, "Готово" if summary.ok else "Завершено с ошибками")
        self.tree.refresh()
        self._update_totals()
        if (
            summary.done
            or summary.skipped
            or summary.failed
            or summary.canceled
            or summary.unavailable
        ):
            messagebox.showinfo(
                "Загрузка завершена",
                f"{summary.as_text()}\nВремя: {summary.elapsed:.1f} с",
            )

    def _log(self, level: str, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{level}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        self.cancel.set()
        self.destroy()


def run_gui() -> int:
    try:
        app = App()
    except ImportError:
        print("Tkinter не установлен. Установите python3-tk (Linux) или tcl/tk (Windows).")
        return 2
    except tk.TclError as exc:
        print(f"GUI недоступен (нет дисплея?): {exc}. Используйте CLI.")
        return 2
    app.mainloop()
    return 0


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
