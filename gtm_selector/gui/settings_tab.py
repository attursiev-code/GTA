"""Вкладка «Параметры»: пороги критериев подбора и экономические параметры."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ..params import Thresholds, EconomicParams, Settings
from ..models import GtmType

THRESHOLD_FIELDS = [
    ("opz_skin_min", "ОПЗ: минимальный скин-фактор для срабатывания"),
    ("opz_skin_ref", "ОПЗ: скин, при котором прирост = 100% от uplift"),
    ("opz_uplift_pct", "ОПЗ: базовый прирост Qн, %"),
    ("grp_perm_max", "ГРП: максимальная проницаемость, мД"),
    ("grp_watercut_max", "ГРП: максимальная обводнённость, %"),
    ("grp_depletion_max", "ГРП: максимальная выработка запасов, %"),
    ("grp_uplift_pct", "ГРП: прирост Qн, %"),
    ("rir_watercut_min", "РИР: минимальная обводнённость, %"),
    ("rir_depletion_max", "РИР: максимальная выработка запасов, %"),
    ("rir_min_history_points", "РИР: минимум точек истории для диагностики Chan"),
    ("rir_spike_ratio", "РИР: порог скачка производной ВНФ (во сколько раз)"),
    ("rir_squeeze_uplift_pct", "РИР (сквозная заливка): прирост Qн, %"),
    ("rir_selective_uplift_pct", "РИР (селективная изоляция): прирост Qн, %"),
    ("rir_interval_switch_uplift_pct", "РИР (перевод на другие интервалы): прирост Qн, %"),
    ("zbs_watercut_min", "ЗБС: минимальная обводнённость, %"),
    ("zbs_reserves_min", "ЗБС: минимальные остаточные запасы, тыс.т"),
    ("zbs_uplift_pct", "ЗБС: прирост Qн, %"),
    ("pump_util_high", "Насос: порог перегрузки (доля от 0 до 1)"),
    ("pump_util_low", "Насос: порог недогрузки (доля от 0 до 1)"),
    ("pump_uplift_pct", "Насос: прирост Qн, %"),
    ("perf_unopened_min", "Доперфорация: мин. доля невскрытой толщины (0-1)"),
    ("perf_reserves_min", "Доперфорация: минимальные остаточные запасы, тыс.т"),
    ("perf_uplift_pct", "Доперфорация: прирост Qн, %"),
    ("reactivation_max_idle_days", "Реактивация: макс. простой, сут"),
    ("reactivation_reserves_min", "Реактивация: минимальные остаточные запасы, тыс.т"),
    ("reactivation_decline_per_100days", "Реактивация: потеря потенциала на 100 сут простоя, %"),
    ("min_months_between_gtm", "Минимум месяцев между ГТМ на одной скважине"),
]

ECON_FIELDS = [
    ("oil_price", "Цена реализации нефти, руб./т"),
    ("opex_per_ton", "Удельные операционные затраты, руб./т"),
    ("effect_duration_months", "Период учёта эффекта, мес."),
    ("monthly_decline_pct", "Темп падения доп. дебита, %/мес."),
]


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self.app = app
        self._vars: dict[str, tk.StringVar] = {}
        self._cost_vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self.load_from_settings()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        thresholds_frame = ScrollableFrame(notebook)
        economics_frame = ScrollableFrame(notebook)
        notebook.add(thresholds_frame, text="Пороги критериев подбора")
        notebook.add(economics_frame, text="Экономические параметры")

        for row, (attr, label) in enumerate(THRESHOLD_FIELDS):
            ttk.Label(thresholds_frame.inner, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=6, pady=3
            )
            var = tk.StringVar()
            ttk.Entry(thresholds_frame.inner, textvariable=var, width=14).grid(
                row=row, column=1, sticky="w", padx=6, pady=3
            )
            self._vars[attr] = var

        for row, (attr, label) in enumerate(ECON_FIELDS):
            ttk.Label(economics_frame.inner, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=6, pady=3
            )
            var = tk.StringVar()
            ttk.Entry(economics_frame.inner, textvariable=var, width=14).grid(
                row=row, column=1, sticky="w", padx=6, pady=3
            )
            self._vars[attr] = var

        base_row = len(ECON_FIELDS)
        ttk.Separator(economics_frame.inner, orient="horizontal").grid(
            row=base_row, column=0, columnspan=2, sticky="ew", pady=8
        )
        ttk.Label(economics_frame.inner, text="Стоимость проведения ГТМ, руб.:", font=("", 10, "bold")).grid(
            row=base_row + 1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4)
        )
        for i, gtm_type in enumerate(GtmType):
            row = base_row + 2 + i
            ttk.Label(economics_frame.inner, text=gtm_type.label + ":").grid(
                row=row, column=0, sticky="w", padx=6, pady=3
            )
            var = tk.StringVar()
            ttk.Entry(economics_frame.inner, textvariable=var, width=14).grid(
                row=row, column=1, sticky="w", padx=6, pady=3
            )
            self._cost_vars[gtm_type.value] = var

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="Применить", command=self.apply_settings).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Сбросить по умолчанию", command=self.reset_defaults).pack(side="left", padx=4)

    def load_from_settings(self):
        t = self.app.settings.thresholds
        e = self.app.settings.economics
        for attr, _ in THRESHOLD_FIELDS:
            self._vars[attr].set(str(getattr(t, attr)))
        for attr, _ in ECON_FIELDS:
            self._vars[attr].set(str(getattr(e, attr)))
        for key, var in self._cost_vars.items():
            var.set(str(e.cost_by_type.get(key, 0.0)))

    def apply_settings(self):
        try:
            t_kwargs = {attr: float(self._vars[attr].get()) for attr, _ in THRESHOLD_FIELDS}
            t_kwargs["reactivation_max_idle_days"] = int(float(t_kwargs["reactivation_max_idle_days"]))
            t_kwargs["min_months_between_gtm"] = int(float(t_kwargs["min_months_between_gtm"]))
            t_kwargs["rir_min_history_points"] = int(float(t_kwargs["rir_min_history_points"]))

            e_kwargs = {attr: float(self._vars[attr].get()) for attr, _ in ECON_FIELDS}
            e_kwargs["effect_duration_months"] = int(float(e_kwargs["effect_duration_months"]))

            cost_by_type = {key: float(var.get()) for key, var in self._cost_vars.items()}
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", f"Проверьте, что все поля — числа.\n{exc}")
            return

        new_thresholds = Thresholds(**t_kwargs)
        new_econ = EconomicParams(**e_kwargs)
        new_econ.cost_by_type = cost_by_type
        self.app.settings = Settings(thresholds=new_thresholds, economics=new_econ)
        self.app.mark_dirty()
        messagebox.showinfo("Параметры", "Параметры применены.")

    def reset_defaults(self):
        if not messagebox.askyesno("Сброс параметров", "Сбросить все параметры к значениям по умолчанию?"):
            return
        self.app.settings = Settings()
        self.load_from_settings()
        self.app.mark_dirty()
