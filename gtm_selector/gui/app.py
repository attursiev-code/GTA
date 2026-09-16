"""Главное окно приложения «Подбор ГТМ»."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..models import Well
from ..params import Settings
from ..data_io import save_project, load_project
from .wells_tab import WellsTab
from .results_tab import ResultsTab
from .settings_tab import SettingsTab

APP_TITLE = "Подбор ГТМ"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x680")
        self.minsize(900, 560)

        self.wells: list[Well] = []
        self.settings: Settings = Settings()
        self.project_path: str | None = None
        self.dirty: bool = False

        self._build_menu()
        self._build_ui()
        self._update_title()

    # -- UI construction -------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Новый проект", command=self.new_project)
        file_menu.add_command(label="Открыть проект...", command=self.open_project)
        file_menu.add_command(label="Сохранить проект", command=self.save_project)
        file_menu.add_command(label="Сохранить как...", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_exit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.config(menu=menubar)
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self.wells_tab = WellsTab(notebook, self)
        self.results_tab = ResultsTab(notebook, self)
        self.settings_tab = SettingsTab(notebook, self)

        notebook.add(self.wells_tab, text="Скважины")
        notebook.add(self.results_tab, text="Подбор ГТМ")
        notebook.add(self.settings_tab, text="Параметры")

        self.wells_tab.refresh()

        self.status_var = tk.StringVar(value="Готово")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom")

    # -- state helpers -----------------------------------------------------
    def mark_dirty(self):
        self.dirty = True
        self._update_title()

    def _update_title(self):
        name = self.project_path or "Без названия"
        star = "*" if self.dirty else ""
        self.title(f"{APP_TITLE} — {name}{star}")

    def set_status(self, text: str):
        self.status_var.set(text)

    # -- file actions --------------------------------------------------
    def _confirm_discard_changes(self) -> bool:
        if not self.dirty:
            return True
        return messagebox.askyesno(
            "Несохранённые изменения",
            "Есть несохранённые изменения. Продолжить без сохранения?",
        )

    def new_project(self):
        if not self._confirm_discard_changes():
            return
        self.wells = []
        self.settings = Settings()
        self.project_path = None
        self.dirty = False
        self.wells_tab.refresh()
        self.settings_tab.load_from_settings()
        self._update_title()
        self.set_status("Создан новый проект")

    def open_project(self):
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(filetypes=[("Проекты ГТМ", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            wells, settings = load_project(path)
        except Exception as exc:
            messagebox.showerror("Ошибка открытия", str(exc))
            return
        self.wells = wells
        self.settings = settings
        self.project_path = path
        self.dirty = False
        self.wells_tab.refresh()
        self.settings_tab.load_from_settings()
        self._update_title()
        self.set_status(f"Открыт проект: {path}")

    def save_project(self):
        if self.project_path is None:
            self.save_project_as()
            return
        save_project(self.project_path, self.wells, self.settings)
        self.dirty = False
        self._update_title()
        self.set_status(f"Проект сохранён: {self.project_path}")

    def save_project_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Проекты ГТМ", "*.json")])
        if not path:
            return
        self.project_path = path
        self.save_project()

    def on_exit(self):
        if self._confirm_discard_changes():
            self.destroy()

    def show_about(self):
        messagebox.showinfo(
            "О программе",
            "Программа подбора геолого-технических мероприятий (ГТМ)\n"
            "Версия 1.0\n\n"
            "Экспертно-экономическая оценка кандидатов на ГТМ "
            "(ОПЗ, ГРП, РИР, ЗБС, смена насоса, доперфорация, реактивация) "
            "по данным о скважинах.",
        )


def run():
    app = App()
    app.mainloop()
