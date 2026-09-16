"""Сборка полного цикла подбора ГТМ: правила + экономика + ранжирование."""

from __future__ import annotations

from .models import Well, Recommendation
from .params import Settings
from .rules import evaluate_well
from .economics import evaluate_economics


def select_gtm(
    wells: list[Well], settings: Settings, only_profitable: bool = True
) -> list[Recommendation]:
    """Выполняет подбор ГТМ по списку скважин.

    Возвращает список рекомендаций, отсортированный по убыванию
    экономического эффекта. Если ``only_profitable`` — оставляет
    только рекомендации с положительным эффектом.
    """
    recommendations: list[Recommendation] = []

    for well in wells:
        candidates = evaluate_well(well, settings.thresholds)
        for candidate in candidates:
            rec = evaluate_economics(well, candidate, settings.economics)
            if only_profitable and rec.economic_effect <= 0:
                continue
            recommendations.append(rec)

    recommendations.sort(key=lambda r: r.economic_effect, reverse=True)
    return recommendations


def best_recommendation_per_well(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """Оставляет только лучшую (по эффекту) рекомендацию на каждую скважину."""
    best: dict[str, Recommendation] = {}
    for rec in recommendations:
        current = best.get(rec.well_id)
        if current is None or rec.economic_effect > current.economic_effect:
            best[rec.well_id] = rec
    result = list(best.values())
    result.sort(key=lambda r: r.economic_effect, reverse=True)
    return result
