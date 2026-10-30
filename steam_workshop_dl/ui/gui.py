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
from tkinter import filedialog, messagebox, ttk

from ..app.downloader import Downloader
from ..app.resolver import Resolver
from ..core.errors import WorkshopError
from ..core.models import ItemStatus, Settings, Summary, WorkshopNode
from ..core.naming import human_size
from ..core.tree import selected_items
from ..services.steam_api import SteamAPI
from .gui_tree import CheckTree


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
        self.messages.put(("status", item_id, status))

    def progress(self, done: int, total: int, current_id: str | None) -> None:
        self.messages.put(("progress", done, total))

    def finished(self, summary: Summary) -> None:
        self.messages.put(("finished", summary))


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Steam Workshop Downloader")
        self.geometry("980x700")
        self.minsize(760, 520)

        self.messages: queue.Queue = queue.Queue()
        self.events = GuiEvents(self.messages)
        self.root_node: WorkshopNode | None = None
        self.worker: threading.Thread | None = None
        self.cancel = threading.Event()

        self.target = tk.StringVar()
        self.output = tk.StringVar(value=str(Path.home() / "Downloads" / "workshop"))
        self.target_type = tk.StringVar(value="collection")
        self.auth_mode = tk.StringVar(value="anonymous")
        self.username = tk.StringVar()
        self.status = tk.StringVar(value="Готов к работе")

        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Тип:").grid(row=0, column=0, sticky="w")
        types = ttk.Frame(top)
        types.grid(row=0, column=1, columnspan=2, sticky="w", padx=(8, 0))
        ttk.Radiobutton(types, text="Коллекция", value="collection", variable=self.target_type).pack(side="left")
        ttk.Radiobutton(types, text="Мод", value="mod", variable=self.target_type).pack(side="left", padx=(12, 0))

        ttk.Label(top, text="Ссылка/ID:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.target).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Label(top, text="Куда:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.output).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(top, text="Выбрать", command=self._choose_output).grid(row=2, column=2, padx=(8, 0), pady=(8, 0))

        auth = ttk.Frame(top)
        auth.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(auth, text="Авторизация:").pack(side="left")
        ttk.Radiobutton(auth, text="Анонимно", value="anonymous", variable=self.auth_mode).pack(side="left", padx=(8, 0))
        login = ttk.Radiobutton(auth, text="Аккаунт (в CLI)", value="login", variable=self.auth_mode)
        login.pack(side="left", padx=(12, 0))
        ttk.Entry(auth, textvariable=self.username, width=18).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(top)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Показать список", command=self._show_list).pack(side="left")
        ttk.Button(actions, text="Скачать выбранное", command=self._download).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Выбрать все", command=lambda: self.tree.select_all(True)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Снять все", command=lambda: self.tree.select_all(False)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Отмена", command=self._cancel).pack(side="right")
        top.columnconfigure(1, weight=1)

        tree_frame = ttk.Frame(self, padding=(10, 0, 10, 0))
        tree_frame.pack(fill="both", expand=True)
        self.tree = CheckTree(tree_frame, on_change=self._update_totals)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        self.progress = ttk.Progressbar(bottom, length=220, mode="determinate")
        self.progress.pack(side="right")

        log_frame = ttk.LabelFrame(self, text="Лог", padding=6)
        log_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=7, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _choose_output(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output.get() or str(Path.home()))
        if chosen:
            self.output.set(chosen)

    def _settings(self) -> Settings:
        return Settings(
            target=self.target.get().strip(),
            target_type=self.target_type.get(),
            output_dir=Path(self.output.get()).expanduser(),
            auth_mode="anonymous",
            username=None,
        )

    def _show_list(self) -> None:
        if self._busy():
            return
        target = self.target.get().strip()
        if not target:
            messagebox.showwarning("Нет ссылки", "Вставьте ссылку или ID.")
            return
        if self.auth_mode.get() == "login":
            messagebox.showinfo(
                "Вход под аккаунтом",
                "В GUI пока доступен только анонимный вход. Используйте CLI с --login.",
            )
            return
        target_type = self.target_type.get()
        self._set_busy(True, "Получение списка…")
        self.cancel.clear()

        def work() -> None:
            try:
                api = SteamAPI()
                root = Resolver(api).resolve(target, target_type, self.events)
                self.messages.put(("preview_done", root))
            except WorkshopError as exc:
                self.messages.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self.messages.put(("error", f"Неожиданная ошибка: {exc}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _download(self) -> None:
        if self._busy() or self.root_node is None:
            return
        if self.auth_mode.get() == "login":
            messagebox.showinfo(
                "Вход под аккаунтом",
                "В GUI пока доступен только анонимный вход. Используйте CLI с --login.",
            )
            return
        items = selected_items(self.root_node)
        if not items:
            messagebox.showinfo("Пусто", "Не выбрано ни одного мода.")
            return
        settings = self._settings()
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        self._set_busy(True, "Загрузка…")
        self.cancel.clear()
        root = self.root_node

        def work() -> None:
            try:
                Downloader().run(
                    settings,
                    root=root,
                    events=self.events,
                    cancel=self.cancel,
                )
            except WorkshopError as exc:
                self.messages.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001
                self.messages.put(("error", f"Неожиданная ошибка: {exc}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _cancel(self) -> None:
        self.cancel.set()
        self._log("info", "Запрошена отмена…")

    def _busy(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def _set_busy(self, busy: bool, text: str) -> None:
        self.status.set(text)

    def _update_totals(self) -> None:
        if self.root_node is None:
            return
        available, selected = self.root_node.counts()
        size = self.root_node.total_size(selected_only=True)
        self.status.set(f"Выбрано {selected} из {available} · {human_size(size)}")

    def _poll(self) -> None:
        try:
            while True:
                message = self.messages.get_nowait()
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
                    self._update_totals()
                    self._set_busy(False, "Список загружен")
                elif kind == "finished":
                    summary = message[1]
                    self._set_busy(False, "Готово")
                    if summary.done or summary.skipped:
                        self._update_totals()
                elif kind == "error":
                    self._set_busy(False, "Ошибка")
                    self._log("error", message[1])
                    messagebox.showerror("Ошибка", message[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)

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
