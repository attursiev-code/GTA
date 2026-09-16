"""Вкладка «Скважины»: таблица скважин и операции над ней."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..models import Well
from ..data_io import load_wells_csv, save_wells_csv
from .well_dialog import WellDialog

COLUMNS = [
    ("id", "№ скв.", 70),
    ("name", "Название", 100),
    ("formation", "Пласт", 70),
    ("status_label", "Статус", 110),
    ("qo", "Qн, т/сут", 80),
    ("ql", "Qж, т/сут", 80),
    ("watercut", "Обв., %", 70),
    ("skin", "Скин", 60),
    ("perm", "k, мД", 60),
    ("reserves_remaining", "Запасы, тыс.т", 90),
    ("depletion", "Выраб., %", 80),
]


class WellsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Добавить", command=self.add_well).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Изменить", command=self.edit_selected).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Удалить", command=self.delete_selected).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(toolbar, text="Импорт CSV...", command=self.import_csv).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Экспорт CSV...", command=self.export_csv).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(toolbar, text="Загрузить пример", command=self.load_sample).pack(side="left", padx=2)

        self.count_label = ttk.Label(toolbar, text="")
        self.count_label.pack(side="right", padx=6)

        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.place(relx=1.0, rely=0.06, relheight=0.88, anchor="ne")

    # -- data helpers ----------------------------------------------------
    @property
    def wells(self) -> list[Well]:
        return self.app.wells

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for well in self.wells:
            self.tree.insert("", "end", iid=well.id, values=(
                well.id, well.name, well.formation, well.status.label,
                f"{well.qo:.1f}", f"{well.ql:.1f}", f"{well.watercut:.1f}",
                f"{well.skin:.1f}", f"{well.perm:.1f}",
                f"{well.reserves_remaining:.1f}", f"{well.depletion:.1f}",
            ))
        self.count_label.config(text=f"Скважин: {len(self.wells)}")

    def _selected_well(self) -> Well | None:
        sel = self.tree.selection()
        if not sel:
            return None
        well_id = sel[0]
        return next((w for w in self.wells if w.id == well_id), None)

    # -- actions -----------------------------------------------------------
    def add_well(self):
        dialog = WellDialog(self)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        if any(w.id == dialog.result.id for w in self.wells):
            messagebox.showerror("Ошибка", f"Скважина с номером {dialog.result.id} уже существует.")
            return
        self.wells.append(dialog.result)
        self.app.mark_dirty()
        self.refresh()

    def edit_selected(self):
        well = self._selected_well()
        if well is None:
            messagebox.showinfo("Выбор скважины", "Выберите скважину в таблице.")
            return
        dialog = WellDialog(self, well)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        idx = self.wells.index(well)
        self.wells[idx] = dialog.result
        self.app.mark_dirty()
        self.refresh()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Выбор скважины", "Выберите скважину(ы) в таблице.")
            return
        if not messagebox.askyesno("Подтверждение", f"Удалить выбранные скважины ({len(sel)})?"):
            return
        ids = set(sel)
        self.app.wells = [w for w in self.wells if w.id not in ids]
        self.app.mark_dirty()
        self.refresh()

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            new_wells = load_wells_csv(path)
        except Exception as exc:
            messagebox.showerror("Ошибка импорта", str(exc))
            return
        existing_ids = {w.id for w in self.wells}
        added, replaced = 0, 0
        for w in new_wells:
            if w.id in existing_ids:
                idx = next(i for i, ww in enumerate(self.wells) if ww.id == w.id)
                self.wells[idx] = w
                replaced += 1
            else:
                self.wells.append(w)
                added += 1
        self.app.mark_dirty()
        self.refresh()
        messagebox.showinfo("Импорт завершён", f"Добавлено: {added}, обновлено: {replaced}")

    def export_csv(self):
        if not self.wells:
            messagebox.showinfo("Экспорт", "Нет данных для экспорта.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV файлы", "*.csv")])
        if not path:
            return
        save_wells_csv(self.wells, path)
        messagebox.showinfo("Экспорт завершён", f"Сохранено скважин: {len(self.wells)}")

    def load_sample(self):
        from ..sample_data import make_sample_wells
        if self.wells and not messagebox.askyesno(
            "Загрузить пример", "Текущий список скважин будет заменён примером. Продолжить?"
        ):
            return
        self.app.wells = make_sample_wells()
        self.app.mark_dirty()
        self.refresh()
