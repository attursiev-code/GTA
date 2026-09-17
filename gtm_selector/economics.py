"""Расчёт экономического эффекта от проведения ГТМ."""

from __future__ import annotations

from .models import Candidate, Recommendation, Well
from .params import EconomicParams

DAYS_PER_MONTH = 30.4


def evaluate_economics(
    well: Well, candidate: Candidate, econ: EconomicParams
) -> Recommendation:
    """Считает прирост добычи, выручку, затраты и эффект по кандидату.

    Для кандидатов с ``matched=False`` (диагностика проведена, но ГТМ не
    рекомендован) экономика не считается — возвращается нулевая рекомендация,
    сохраняющая механизм и обоснование для отображения пользователю.
    """
    if not candidate.matched:
        return Recommendation(
            well_id=well.id,
            well_name=well.name,
            gtm_type=candidate.gtm_type,
            reasons=list(candidate.reasons),
            delta_qo=0.0,
            incremental_production=0.0,
            revenue=0.0,
            cost=0.0,
            economic_effect=0.0,
            payback_months=None,
            roi=None,
            matched=False,
            mechanism=candidate.mechanism,
            notes=list(candidate.notes),
        )

    decline = max(0.0, min(econ.monthly_decline_pct / 100.0, 0.9))
    months = max(1, econ.effect_duration_months)

    monthly_rate = candidate.delta_qo * DAYS_PER_MONTH
    cumulative_production = 0.0
    cumulative_revenue = 0.0
    payback_months = None
    cost = econ.cost_for(candidate.gtm_type)

    for month in range(1, months + 1):
        production_this_month = monthly_rate * ((1.0 - decline) ** (month - 1))
        cumulative_production += production_this_month
        cumulative_revenue += production_this_month * econ.netback
        if payback_months is None and cumulative_revenue >= cost and cost > 0:
            payback_months = float(month)

    economic_effect = cumulative_revenue - cost
    roi = (economic_effect / cost) if cost > 0 else None

    return Recommendation(
        well_id=well.id,
        well_name=well.name,
        gtm_type=candidate.gtm_type,
        reasons=list(candidate.reasons),
        delta_qo=candidate.delta_qo,
        incremental_production=cumulative_production,
        revenue=cumulative_revenue,
        cost=cost,
        economic_effect=economic_effect,
        payback_months=payback_months,
        roi=roi,
        matched=True,
        mechanism=candidate.mechanism,
        notes=list(candidate.notes),
    )
