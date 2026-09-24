"""Сборка потока подбора ГТМ: правила диагностики РИР (без экономики).

Экономический блок (``economics.evaluate_economics``) в этот поток сейчас
не подключён — модуль ``economics.py`` сохранён для будущего использования
(когда появятся актуальные цены), но здесь не вызывается.
"""

from __future__ import annotations

from .models import Candidate, Well
from .params import Settings
from .rules import evaluate_well


def select_gtm(wells: list[Well], settings: Settings) -> list[Candidate]:
    """Выполняет подбор ГТМ (сейчас — только диагностика РИР) по списку скважин.

    Возвращает список кандидатов с привязкой к скважине (``well_id``/
    ``well_name``), включая явно не рекомендованные случаи (``matched=False``).
    """
    results: list[Candidate] = []

    for well in wells:
        for candidate in evaluate_well(well, settings.thresholds):
            candidate.well_id = well.id
            candidate.well_name = well.name
            results.append(candidate)

    return results


def best_recommendation_per_well(results: list[Candidate]) -> list[Candidate]:
    """Оставляет одну запись на скважину.

    Без экономики нет критерия «лучше/хуже» для выбора между несколькими
    кандидатами по одной скважине (сейчас РИР и так даёт не более одного
    кандидата на скважину) — оставляется первый встреченный.
    """
    best: dict[str, Candidate] = {}
    for r in results:
        best.setdefault(r.well_id, r)
    return list(best.values())
