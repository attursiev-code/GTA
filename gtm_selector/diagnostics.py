"""Диагностика механизма обводнения скважины по методу Chan (SPE 30775, 1995).

Метод Chan классифицирует источник обводнения по форме кривой водонефтяного
фактора (ВНФ = Qв/Qн) и её производной по времени: изолированный экстремальный
скачок производной указывает на прорыв воды вблизи забоя (негерметичность
колонны, трещина), устойчиво нарастающая производная — на заколонный переток
по промытому каналу, несколько повторяющихся пиков — на неравномерную
выработку нескольких пропластков, а спад производной после начального
роста — на конусообразование (для конуса РИР не показан: конус лечится
изменением режима отбора, а не изоляцией интервала).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .models import ProductionPoint

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d")


class WaterMechanism(str, Enum):
    NEAR_WELLBORE = "near_wellbore"
    CHANNELING = "channeling"
    CONING = "coning"
    MULTILAYER = "multilayer"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class DiagnosticResult:
    """Результат диагностики механизма обводнения по методу Chan."""

    mechanism: WaterMechanism
    confidence: float
    reasons: list[str] = field(default_factory=list)
    wor_series: list[float] = field(default_factory=list)
    wor_prime_series: list[float] = field(default_factory=list)


def _parse_date(date_str: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Не удалось разобрать дату истории добычи: {date_str!r}")


def _linear_trend(series: list[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(series) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, series))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den else 0.0


def _local_maxima_count(series: list[float], baseline: float) -> int:
    threshold = baseline * 3.0 if baseline > 0 else 0.0
    count = 0
    for i in range(1, len(series) - 1):
        if series[i] > series[i - 1] and series[i] > series[i + 1] and series[i] > threshold:
            count += 1
    return count


def classify_water_mechanism(
    history: list[ProductionPoint],
    min_points: int = 6,
    spike_ratio: float = 8.0,
) -> DiagnosticResult:
    """Классифицирует механизм обводнения скважины по истории добычи.

    Строит ряд ВНФ = Qв/Qн и его производную по времени, затем сопоставляет
    форму кривой с типовыми диагностическими признаками метода Chan.
    """
    valid = [p for p in history if p.qo > 0]
    valid.sort(key=lambda p: p.date)

    if len(valid) < min_points:
        return DiagnosticResult(
            mechanism=WaterMechanism.INSUFFICIENT_DATA,
            confidence=0.0,
            reasons=[
                f"Недостаточно точек истории добычи для диагностики Chan: "
                f"{len(valid)} < {min_points}"
            ],
        )

    t0 = _parse_date(valid[0].date)
    days = [(_parse_date(p.date) - t0).days for p in valid]
    wor = [p.qw / p.qo for p in valid]

    wor_prime = [0.0]
    for i in range(1, len(wor)):
        dt = days[i] - days[i - 1]
        wor_prime.append((wor[i] - wor[i - 1]) / dt if dt > 0 else 0.0)

    analysis = wor_prime[1:]
    if not analysis:
        return DiagnosticResult(
            mechanism=WaterMechanism.INSUFFICIENT_DATA,
            confidence=0.0,
            reasons=["Недостаточно интервалов между точками для расчёта производной ВНФ"],
            wor_series=wor,
            wor_prime_series=wor_prime,
        )

    abs_vals = [abs(v) for v in analysis]
    lower_half = sorted(abs_vals)[: max(1, len(abs_vals) // 2)]
    baseline_avg = sum(lower_half) / len(lower_half) if lower_half else 0.0
    peak_val = max(abs_vals)
    peak_idx = abs_vals.index(peak_val)

    # 1. Изолированный экстремальный скачок производной ВНФ -> NEAR_WELLBORE
    spike_threshold = spike_ratio * baseline_avg
    is_isolated_spike = (
        baseline_avg > 0
        and peak_val >= spike_threshold
        and sum(1 for v in abs_vals if v >= spike_threshold * 0.5) <= 2
    )
    if is_isolated_spike:
        reasons = [
            f"Изолированный экстремальный скачок производной ВНФ "
            f"(d(ВНФ)/dt = {analysis[peak_idx]:.4f} на точке №{peak_idx + 2}) "
            f"превышает фоновый уровень ({baseline_avg:.4f}) в "
            f"{peak_val / baseline_avg:.1f} раз (порог {spike_ratio:.1f}) — "
            "признак локального прорыва воды вблизи забоя (негерметичность "
            "колонны/трещина)"
        ]
        return DiagnosticResult(WaterMechanism.NEAR_WELLBORE, 0.85, reasons, wor, wor_prime)

    # 2. Несколько повторяющихся локальных пиков производной -> MULTILAYER
    peaks = _local_maxima_count(analysis, baseline_avg)
    if peaks >= 2:
        reasons = [
            f"Выявлено {peaks} повторяющихся локальных пика производной ВНФ — "
            "признак неравномерной, чередующейся выработки нескольких "
            "пропластков многопластовой системы"
        ]
        return DiagnosticResult(WaterMechanism.MULTILAYER, 0.7, reasons, wor, wor_prime)

    # 3. Устойчиво положительный тренд производной -> CHANNELING
    positive_share = sum(1 for v in analysis if v > 0) / len(analysis)
    slope = _linear_trend(analysis)
    if positive_share >= 0.7 and slope >= 0:
        reasons = [
            f"Производная ВНФ устойчиво положительна ({positive_share * 100:.0f}% "
            f"точек, тренд {slope:+.5f}/сут) на всём периоде наблюдения — "
            "признак прогрессирующего прорыва воды по промытому каналу "
            "(заколонный переток)"
        ]
        return DiagnosticResult(WaterMechanism.CHANNELING, 0.75, reasons, wor, wor_prime)

    # 4. Спад производной после начального роста -> CONING
    half = len(analysis) // 2
    if half > 0:
        first_half_avg = sum(analysis[:half]) / half
        second_half_avg = sum(analysis[half:]) / (len(analysis) - half)
        if first_half_avg > 0 and second_half_avg < first_half_avg * 0.5:
            reasons = [
                "После начального роста производная ВНФ идёт на спад "
                f"(среднее по первой половине периода {first_half_avg:.4f}, "
                f"по второй {second_half_avg:.4f}) — форма кривой характерна "
                "для конусообразования; РИР в этом случае не показан — конус "
                "лечится сменой режима отбора, а не изоляцией интервала"
            ]
            return DiagnosticResult(WaterMechanism.CONING, 0.65, reasons, wor, wor_prime)

    reasons = ["Форма кривой ВНФ и её производной не выявляет выраженной аномалии обводнения"]
    return DiagnosticResult(WaterMechanism.STABLE, 0.5, reasons, wor, wor_prime)
