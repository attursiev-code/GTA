"""Диалог добавления/редактирования скважины."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

from ..models import GRP_STATUS_LABELS, GRP_STATUS_LABELS_REVERSE, Well, WellStatus

_GRP_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y")


def _parse_grp_date(text: str) -> str | None:
    """Разбирает дату ГРП (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ) в ГГГГ-ММ-ДД, либо None."""
    for fmt in _GRP_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


FIELD_SPECS = [
    ("id", "Номер скважины", "str"),
    ("name", "Название", "str"),
    ("formation", "Пласт", "str"),
    ("status", "Статус", "status"),
    ("qo", "Дебит нефти Qн, т/сут", "float"),
    ("ql", "Дебит жидкости Qж, т/сут", "float"),
    ("watercut", "Обводнённость, %", "float"),
    ("p_res", "Пластовое давление, атм", "float"),
    ("p_res_initial", "Начальное пласт. давление, атм", "float"),
    ("p_wf", "Забойное давление, атм", "float"),
    ("skin", "Скин-фактор", "float"),
    ("perm", "Проницаемость, мД", "float"),
    ("thickness_total", "Общая н/нас. толщина, м", "float"),
    ("thickness_perforated", "Вскрытая перфорацией толщина, м", "float"),
    ("reserves_remaining", "Остаточные запасы, тыс.т", "float"),
    ("depletion", "Выработка запасов, %", "float"),
    ("pump_capacity", "Производительность насоса, т/сут", "float"),
    ("idle_days", "Простой, сут", "int"),
    ("last_active_qo", "Дебит нефти до остановки, т/сут", "float"),
    ("months_since_last_gtm", "Месяцев с последнего ГТМ", "int"),
    ("notes", "Примечание", "str"),
    ("grp_status", "ГРП", "grp_status"),
    ("grp_date", "Дата ГРП", "date_optional"),
]


class WellDialog(tk.Toplevel):
    """Модальный диалог для создания или редактирования скважины."""

    def __init__(self, parent, well: Well | None = None):
        super().__init__(parent)
        self.title("Скважина" if well is None else f"Скважина {well.id}")
        self.resizable(False, False)
        self.transient(parent)
        self.result: Well | None = None
        self._vars: dict[str, tk.Variable] = {}
        self._build_form(well)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_form(self, well: Well | None):
        container = ttk.Frame(self, padding=12)
        container.grid(row=0, column=0, sticky="nsew")

        ncols = 2
        for idx, (attr, label, kind) in enumerate(FIELD_SPECS):
            row = idx // ncols
            col = (idx % ncols) * 2
            ttk.Label(container, text=label + ":").grid(row=row, column=col, sticky="w", padx=4, pady=3)

            default = getattr(well, attr) if well is not None else getattr(Well.__dataclass_fields__[attr], "default", "")

            if kind == "status":
                var = tk.StringVar(value=(well.status.label if well else WellStatus.ACTIVE.label))
                combo = ttk.Combobox(
                    container, textvariable=var, state="readonly",
                    values=[WellStatus.ACTIVE.label, WellStatus.IDLE.label], width=22,
                )
                combo.grid(row=row, column=col + 1, sticky="w", padx=4, pady=3)
            elif kind == "grp_status":
                current = well.grp_status if well is not None else "unknown"
                label_value = GRP_STATUS_LABELS.get(current, GRP_STATUS_LABELS["unknown"])
                var = tk.StringVar(value=label_value)
                combo = ttk.Combobox(
                    container, textvariable=var, state="readonly",
                    values=list(GRP_STATUS_LABELS.values()), width=22,
                )
                combo.grid(row=row, column=col + 1, sticky="w", padx=4, pady=3)
            else:
                value = getattr(well, attr) if well is not None else default
                var = tk.StringVar(value=str(value))
                entry = ttk.Entry(container, textvariable=var, width=24)
                entry.grid(row=row, column=col + 1, sticky="w", padx=4, pady=3)

            self._vars[attr] = var

        btn_row = (len(FIELD_SPECS) // ncols) + 1
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=btn_row, column=0, columnspan=4, pady=(12, 0), sticky="e")
        ttk.Button(btn_frame, text="Отмена", command=self._on_cancel).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Сохранить", command=self._on_save).pack(side="right", padx=4)

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_save(self):
        data: dict = {}
        try:
            for attr, label, kind in FIELD_SPECS:
                raw = self._vars[attr].get()
                if kind == "float":
                    data[attr] = float(raw) if raw.strip() != "" else 0.0
                elif kind == "int":
                    data[attr] = int(float(raw)) if raw.strip() != "" else 0
                elif kind == "status":
                    data[attr] = WellStatus.ACTIVE if raw == WellStatus.ACTIVE.label else WellStatus.IDLE
                elif kind == "grp_status":
                    data[attr] = GRP_STATUS_LABELS_REVERSE.get(raw, "unknown")
                elif kind == "date_optional":
                    text = raw.strip()
                    if text == "":
                        data[attr] = ""
                    else:
                        parsed = _parse_grp_date(text)
                        if parsed is None:
                            messagebox.showerror(
                                "Ошибка ввода",
                                f"Не удалось разобрать «{label}»: {raw!r}. "
                                "Используйте формат ГГГГ-ММ-ДД или ДД.ММ.ГГГГ.",
                                parent=self,
                            )
                            return
                        data[attr] = parsed
                else:
                    data[attr] = raw
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", f"Проверьте числовые поля.\n{exc}", parent=self)
            return

        if not data.get("id", "").strip():
            messagebox.showerror("Ошибка ввода", "Номер скважины обязателен.", parent=self)
            return

        # ГРП не "Проводился", а дата всё же заполнена — не блокируем сохранение,
        # просто не сохраняем дату (не относится к делу).
        if data.get("grp_status") != "yes":
            data["grp_date"] = ""

        self.result = Well.from_dict(data)
        self.destroy()
