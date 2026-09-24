"""Вкладка «Подбор ГТМ»: запуск подбора и просмотр рекомендаций."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..models import GtmType, GTM_LABELS
from ..engine import select_gtm, best_recommendation_per_well
from ..data_io import save_recommendations_csv

COLUMNS = [
    ("well_id", "№ скв.", 70),
    ("well_name", "Название", 100),
    ("gtm_label", "Рекомендуемое ГТМ", 220),
    ("mechanism", "Механизм обводнения", 190),
]


class ResultsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self.app = app
        self.recommendations = []
        self._build_ui()

    def _build_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Выполнить подбор", command=self.run_selection).pack(side="left", padx=2)

        self.best_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar, text="Лучшее ГТМ на скважину", variable=self.best_only,
            command=self.run_selection,
        ).pack(side="left", padx=8)

        ttk.Label(toolbar, text="Тип ГТМ:").pack(side="left", padx=(12, 2))
        self.type_filter = tk.StringVar(value="Все")
        type_values = ["Все"] + [t.label for t in GtmType]
        self.type_combo = ttk.Combobox(
            toolbar, textvariable=self.type_filter, values=type_values,
            state="readonly", width=32,
        )
        self.type_combo.pack(side="left")
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(toolbar, text="Экспорт CSV...", command=self.export_csv).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Обоснование", command=self.show_reasons).pack(side="left", padx=2)

        self.summary_label = ttk.Label(toolbar, text="")
        self.summary_label.pack(side="right", padx=6)

        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.show_reasons())
        self.tree.tag_configure("not_recommended", foreground="#888888")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.place(relx=1.0, rely=0.06, relheight=0.88, anchor="ne")

    # -- actions -------------------------------------------------------
    def run_selection(self):
        wells = self.app.wells
        if not wells:
            messagebox.showinfo("Подбор ГТМ", "Список скважин пуст. Добавьте или импортируйте скважины.")
            self.recommendations = []
            self._populate([])
            return
        recs = select_gtm(wells, self.app.settings)
        if self.best_only.get():
            recs = best_recommendation_per_well(recs)
        self.recommendations = recs
        self._apply_filter()

    def _apply_filter(self):
        label = self.type_filter.get()
        if label == "Все":
            filtered = self.recommendations
        else:
            # Не рекомендованные (диагностированные, но matched=False) случаи
            # показываем только в общем списке «Все» — у них нет содержательного
            # gtm_type, только служебная заглушка.
            gtm_type = next(t for t in GtmType if t.label == label)
            filtered = [r for r in self.recommendations if r.matched and r.gtm_type == gtm_type]
        self._populate(filtered)

    def _populate(self, recs):
        self.tree.delete(*self.tree.get_children())
        not_recommended = 0
        for i, r in enumerate(recs):
            iid = str(i)
            tags = () if r.matched else ("not_recommended",)
            self.tree.insert("", "end", iid=iid, tags=tags, values=(
                r.well_id, r.well_name, r.gtm_label, r.mechanism or "—",
            ))
            if not r.matched:
                not_recommended += 1
        self._filtered = recs
        self.summary_label.config(
            text=f"Рекомендаций: {len(recs) - not_recommended}   Не рекомендуется: {not_recommended}"
        )

    def show_reasons(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Обоснование", "Выберите строку в таблице.")
            return
        idx = int(sel[0])
        rec = self._filtered[idx]

        lines = [f"Механизм обводнения: {rec.mechanism or '—'}", ""]
        lines.append("Обоснование:")
        if rec.reasons:
            lines.extend(f"• {r}" for r in rec.reasons)
        else:
            lines.append("Нет данных об обосновании.")
        if rec.notes:
            lines.append("")
            lines.append("Технические детали диагностики:")
            lines.extend(f"• {n}" for n in rec.notes)
        text = "\n".join(lines)
        messagebox.showinfo(
            f"Обоснование: {rec.well_name} — {rec.gtm_label}",
            text,
        )

    def export_csv(self):
        if not getattr(self, "_filtered", None):
            messagebox.showinfo("Экспорт", "Нет данных для экспорта. Выполните подбор.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV файлы", "*.csv")])
        if not path:
            return
        save_recommendations_csv(self._filtered, path)
        messagebox.showinfo("Экспорт завершён", f"Сохранено рекомендаций: {len(self._filtered)}")
