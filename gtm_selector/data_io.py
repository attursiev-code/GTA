"""Импорт/экспорт скважин (CSV) и сохранение/загрузка проекта (JSON)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Well, Recommendation
from .params import Settings

WELL_FIELDS = [
    "id", "name", "formation", "status",
    "qo", "ql", "watercut",
    "p_res", "p_res_initial", "p_wf",
    "skin", "perm", "thickness_total", "thickness_perforated",
    "reserves_remaining", "depletion",
    "pump_capacity", "idle_days", "last_active_qo", "months_since_last_gtm",
    "notes",
]

_NUMERIC_FIELDS = {
    "qo", "ql", "watercut", "p_res", "p_res_initial", "p_wf", "skin", "perm",
    "thickness_total", "thickness_perforated", "reserves_remaining",
    "depletion", "pump_capacity", "last_active_qo",
}
_INT_FIELDS = {"idle_days", "months_since_last_gtm"}


def load_wells_csv(path: str | Path) -> list[Well]:
    wells: list[Well] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data = {}
            for key, value in row.items():
                if key is None:
                    continue
                key = key.strip()
                if value is None:
                    value = ""
                value = value.strip()
                if key in _NUMERIC_FIELDS:
                    data[key] = float(value) if value != "" else 0.0
                elif key in _INT_FIELDS:
                    data[key] = int(float(value)) if value != "" else 0
                else:
                    data[key] = value
            wells.append(Well.from_dict(data))
    return wells


def save_wells_csv(wells: list[Well], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=WELL_FIELDS)
        writer.writeheader()
        for well in wells:
            d = well.to_dict()
            writer.writerow({k: d.get(k, "") for k in WELL_FIELDS})


def save_recommendations_csv(recs: list[Recommendation], path: str | Path) -> None:
    fieldnames = [
        "well_id", "well_name", "gtm_type", "gtm_label",
        "delta_qo", "incremental_production", "revenue", "cost",
        "economic_effect", "payback_months", "roi", "reasons",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in recs:
            writer.writerow({
                "well_id": r.well_id,
                "well_name": r.well_name,
                "gtm_type": r.gtm_type.value,
                "gtm_label": r.gtm_label,
                "delta_qo": round(r.delta_qo, 2),
                "incremental_production": round(r.incremental_production, 1),
                "revenue": round(r.revenue, 0),
                "cost": round(r.cost, 0),
                "economic_effect": round(r.economic_effect, 0),
                "payback_months": r.payback_months,
                "roi": round(r.roi, 2) if r.roi is not None else "",
                "reasons": "; ".join(r.reasons),
            })


def save_project(path: str | Path, wells: list[Well], settings: Settings) -> None:
    payload = {
        "wells": [w.to_dict() for w in wells],
        "settings": settings.to_dict(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_project(path: str | Path) -> tuple[list[Well], Settings]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    wells = [Well.from_dict(d) for d in payload.get("wells", [])]
    settings = Settings.from_dict(payload.get("settings", {}))
    return wells, settings
