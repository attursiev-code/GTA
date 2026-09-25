"""Диагностика механизма обводнения скважины по методу Chan (SPE 30775, 1995).

Метод Chan классифицирует источник обводнения по форме кривой водонефтяного
фактора (ВНФ = Qв/Qн) и её производной по времени: изолированный экстремальный
скачок производной указывает на прорыв воды вблизи забоя (негерметичность
колонны, трещина), устойчиво нарастающая производная — на заколонный переток
по промытому каналу, несколько повторяющихся значимых пиков (при не чисто
монотонном тренде) — на неравномерную выработку нескольких пропластков, а
спад производной после начального роста — на конусообразование (для конуса
РИР не показан: конус лечится изменением режима отбора, а не изоляцией
интервала).

Перед расчётом производной ряд ВНФ сглаживается скользящим средним, чтобы
помесячный шум промысловых данных не давал ложных локальных пиков.

Дополнительно (не как отдельный диагноз, а как подтверждающий признак поверх
уже поставленного) сравнивается начальная и текущая продуктивность скважины
по дебиту нефти (``check_productivity_decline``) — сильное падение дебита
усиливает уверенность в том, что диагностированное обводнение действительно
снижает продуктивность.

Термин «ВНФ» — это внутренняя расчётная величина (не насыщается при
приближении к 100% обводнённости, в отличие от процента). Весь текст,
который увидит пользователь (``reasons``/``notes`` в ``DiagnosticResult``),
формулируется только через обводнённость в процентах/процентных пунктах.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .models import ProductionPoint

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d")
_SMOOTHING_WINDOW = 3
_MULTILAYER_PEAK_FACTOR_MIN = 3.0  # минимальный множитель фона для "значимого" пика


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
    notes: list[str] = field(default_factory=list)
    productivity: dict | None = None


def _parse_date(date_str: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Не удалось разобрать дату истории добычи: {date_str!r}")


def _moving_average(series: list[float], window: int = 3) -> list[float]:
    """Скользящее среднее с усечённым окном на краях ряда."""
    n = len(series)
    if n == 0:
        return []
    half = window // 2
    smoothed = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        segment = series[lo:hi]
        smoothed.append(sum(segment) / len(segment))
    return smoothed


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


def _significant_peak_indices(series: list[float], threshold: float) -> list[int]:
    """Индексы локальных максимумов |series[i]|, превышающих threshold."""
    indices = []
    for i in range(1, len(series) - 1):
        if series[i] > series[i - 1] and series[i] > series[i + 1] and abs(series[i]) > threshold:
            indices.append(i)
    return indices


def _watercut_pct(p: ProductionPoint) -> float:
    """Обводнённость точки истории в процентах: Qв/(Qн+Qв)*100."""
    total = p.qo + p.qw
    return (100.0 * p.qw / total) if total > 0 else 0.0


def _watercut_rate_per_month(watercut_series: list[float], days: list[int], i0: int, i1: int) -> float:
    """Средний темп изменения обводнённости между точками i0 и i1, в п.п./мес."""
    dt = days[i1] - days[i0]
    return ((watercut_series[i1] - watercut_series[i0]) / dt * 30.4) if dt > 0 else 0.0


def check_productivity_decline(
    history: list[ProductionPoint],
    decline_threshold_pct: float = 40.0,
) -> dict:
    """Сравнивает начальную и текущую продуктивность скважины по дебиту нефти.

    Это не отдельный диагноз, а дополнительный подтверждающий признак поверх
    уже поставленного диагноза механизма обводнения: сильное падение дебита
    нефти с начала истории подтверждает, что обводнение действительно снижает
    продуктивность (а не является статистическим шумом на фоне стабильного
    дебита). Начальный дебит усредняется по первым 2-3 точкам (чтобы
    сгладить случайный первый замер), текущий — по последним 2-3 точкам.
    """
    valid = sorted((p for p in history if p.qo > 0), key=lambda p: p.date)

    if len(valid) < 4:
        return {
            "initial_qo": 0.0,
            "current_qo": 0.0,
            "decline_pct": 0.0,
            "significant": False,
            "note": (
                f"Недостаточно точек истории (< 4) для оценки падения "
                f"продуктивности: {len(valid)}"
            ),
        }

    window = 3 if len(valid) >= 6 else 2
    initial_pts = valid[:window]
    current_pts = valid[-window:]
    initial_qo = sum(p.qo for p in initial_pts) / len(initial_pts)
    current_qo = sum(p.qo for p in current_pts) / len(current_pts)

    decline_pct = ((initial_qo - current_qo) / initial_qo * 100.0) if initial_qo > 0 else 0.0
    significant = decline_pct >= decline_threshold_pct

    note = (
        f"Начальный дебит нефти составлял {initial_qo:.1f} т/сут, текущий — "
        f"{current_qo:.1f} т/сут (падение на {decline_pct:.0f}%) — подтверждает, "
        "что проблема обводнения существенно снизила продуктивность скважины"
    )

    return {
        "initial_qo": initial_qo,
        "current_qo": current_qo,
        "decline_pct": decline_pct,
        "significant": significant,
        "note": note,
    }


def classify_water_mechanism(
    history: list[ProductionPoint],
    min_points: int = 6,
    spike_ratio: float = 8.0,
) -> DiagnosticResult:
    """Классифицирует механизм обводнения скважины по истории добычи.

    Внутренне строит ряд ВНФ = Qв/Qн (отношение воды к нефти — в отличие от
    процента обводнённости не насыщается при приближении к 100% и остаётся
    информативным на высокой обводнённости), сглаживает его скользящим
    средним и считает производную по времени, сопоставляя форму кривой с
    типовыми диагностическими признаками метода Chan. Весь текст, который
    видит пользователь (reasons/notes), формулируется только через проценты
    обводнённости — внутренний расчёт на ВНФ сам по себе не показывается.
    """
    notes: list[str] = []

    raw_count = len(history)
    valid = [p for p in history if p.qo > 0]
    valid.sort(key=lambda p: p.date)
    notes.append(
        f"Исходных точек истории: {raw_count}; после фильтрации (Qн > 0): {len(valid)}"
    )

    if len(valid) < min_points:
        notes.append(f"Недостаточно точек для диагностики: {len(valid)} < {min_points}")
        return DiagnosticResult(
            mechanism=WaterMechanism.INSUFFICIENT_DATA,
            confidence=0.0,
            reasons=[
                f"Недостаточно точек истории добычи для диагностики Chan: "
                f"{len(valid)} < {min_points}"
            ],
            notes=notes,
        )

    # Дополнительный подтверждающий признак (не меняет диагноз механизма,
    # только усиливает/ослабляет уверенность в нём) — сравнение начальной и
    # текущей продуктивности скважины по дебиту нефти.
    productivity = check_productivity_decline(valid)

    t0 = _parse_date(valid[0].date)
    days = [(_parse_date(p.date) - t0).days for p in valid]
    wor_raw = [p.qw / p.qo for p in valid]
    # Параллельный ряд обводнённости (%) для текста, который видит пользователь —
    # исходные (несглаженные) значения, а не производная ВНФ.
    watercut_series = [_watercut_pct(p) for p in valid]

    wor_smoothed = _moving_average(wor_raw, window=_SMOOTHING_WINDOW)

    wor_prime = [0.0]
    for i in range(1, len(wor_smoothed)):
        dt = days[i] - days[i - 1]
        wor_prime.append((wor_smoothed[i] - wor_smoothed[i - 1]) / dt if dt > 0 else 0.0)

    analysis = wor_prime[1:]
    if not analysis:
        notes.append("Недостаточно интервалов между точками для оценки динамики обводнённости")
        return DiagnosticResult(
            mechanism=WaterMechanism.INSUFFICIENT_DATA,
            confidence=0.0,
            reasons=["Недостаточно интервалов между точками для оценки динамики обводнённости"],
            wor_series=wor_raw,
            wor_prime_series=wor_prime,
            notes=notes,
        )

    abs_vals = [abs(v) for v in analysis]
    lower_half = sorted(abs_vals)[: max(1, len(abs_vals) // 2)]
    baseline_avg = sum(lower_half) / len(lower_half) if lower_half else 0.0
    peak_val = max(abs_vals)
    peak_idx = abs_vals.index(peak_val)

    positive_share = sum(1 for v in analysis if v > 0) / len(analysis)
    slope = _linear_trend(analysis)
    is_monotonic_trend = positive_share >= 0.85 or positive_share <= 0.15

    # Технический блок обоснования — только в процентах обводнённости и
    # процентных пунктах (сам расчёт выше остаётся на ВНФ, здесь только текст).
    wc_avg_rate_per_month = _watercut_rate_per_month(watercut_series, days, 0, len(valid) - 1)
    notes.append(
        f"Средний темп роста обводнённости за период: {wc_avg_rate_per_month:+.2f} п.п./мес"
    )
    max_jump_idx, max_jump = None, 0.0
    for i in range(1, len(watercut_series)):
        jump = watercut_series[i] - watercut_series[i - 1]
        if abs(jump) > abs(max_jump):
            max_jump, max_jump_idx = jump, i
    if max_jump_idx is not None:
        notes.append(
            f"Максимальный зафиксированный скачок обводнённости: с "
            f"{watercut_series[max_jump_idx - 1]:.1f}% до {watercut_series[max_jump_idx]:.1f}% "
            f"за один отчётный период ({valid[max_jump_idx].date})"
        )

    # 1. Изолированный экстремальный скачок производной ВНФ -> NEAR_WELLBORE
    #    (текст — через скачок обводнённости в этой же точке, а не через ВНФ)
    spike_threshold = spike_ratio * baseline_avg
    is_isolated_spike = (
        baseline_avg > 0
        and peak_val >= spike_threshold
        and sum(1 for v in abs_vals if v >= spike_threshold * 0.5) <= 2
    )
    if is_isolated_spike:
        # Смотрим на реальный (несглаженный) скачок обводнённости, а не на точку
        # максимума сглаженной производной — сглаживание может «размазать» пик
        # по соседним переходам и сдвинуть его относительно фактического выброса.
        if max_jump_idx is not None:
            wc_before, wc_after, jump_pp = watercut_series[max_jump_idx - 1], watercut_series[max_jump_idx], max_jump
            spike_date = valid[max_jump_idx].date
        else:
            wc_before, wc_after = watercut_series[peak_idx], watercut_series[peak_idx + 1]
            jump_pp = wc_after - wc_before
            spike_date = valid[peak_idx + 1].date
        direction = "подскочила" if jump_pp >= 0 else "упала"
        reasons = [
            f"Обводнённость резко {direction} на {abs(jump_pp):.1f} процентных пункта "
            f"за один отчётный период (с {wc_before:.1f}% до {wc_after:.1f}%, {spike_date}) — "
            "признак локального прорыва воды вблизи забоя (негерметичность "
            "колонны/трещина)"
        ]
        return DiagnosticResult(
            WaterMechanism.NEAR_WELLBORE, 0.85, reasons, wor_raw, wor_prime, notes,
            productivity=productivity,
        )

    # 2. Устойчиво положительный тренд производной -> CHANNELING.
    #    Проверяется раньше подсчёта пиков: общий тренд важнее локальных колебаний.
    if positive_share >= 0.7 and slope >= 0:
        reasons = [
            f"Обводнённость устойчиво растёт на всём периоде наблюдения — с "
            f"{watercut_series[0]:.1f}% до {watercut_series[-1]:.1f}% (в среднем "
            f"{wc_avg_rate_per_month:+.2f} п.п./мес) — признак прогрессирующего прорыва "
            "воды по промытому каналу (заколонный переток)"
        ]
        return DiagnosticResult(
            WaterMechanism.CHANNELING, 0.75, reasons, wor_raw, wor_prime, notes,
            productivity=productivity,
        )

    # 3. Несколько повторяющихся значимых пиков производной -> MULTILAYER.
    #    Значимым считается пик, где |ВНФ'| превышает фон минимум в 3-4 раза
    #    (доля от spike_ratio, но не менее 3.0), и только если общий тренд
    #    не является чисто монотонным (иначе это уже CHANNELING/спад, а не
    #    чередующаяся выработка нескольких пропластков).
    peak_factor = max(_MULTILAYER_PEAK_FACTOR_MIN, spike_ratio / 2.0)
    peak_threshold = baseline_avg * peak_factor
    peak_indices = _significant_peak_indices(analysis, peak_threshold)
    significant_peaks = len(peak_indices)
    if not is_monotonic_trend and significant_peaks >= 2:
        episodes = [
            f"с {watercut_series[k]:.1f}% до {watercut_series[k + 1]:.1f}% ({valid[k + 1].date})"
            for k in peak_indices
        ]
        reasons = [
            f"Выявлено {significant_peaks} эпизода(ов) резкого роста обводнённости за период "
            f"без выраженного монотонного тренда: {'; '.join(episodes)} — признак "
            "неравномерной, чередующейся выработки нескольких пропластков многопластовой системы"
        ]
        return DiagnosticResult(
            WaterMechanism.MULTILAYER, 0.7, reasons, wor_raw, wor_prime, notes,
            productivity=productivity,
        )

    # 4. Спад производной после начального роста -> CONING
    half = len(analysis) // 2
    if half > 0:
        first_half_avg = sum(analysis[:half]) / half
        second_half_avg = sum(analysis[half:]) / (len(analysis) - half)
        if first_half_avg > 0 and second_half_avg < first_half_avg * 0.5:
            mid = half
            rate_first = _watercut_rate_per_month(watercut_series, days, 0, mid)
            rate_second = _watercut_rate_per_month(watercut_series, days, mid, len(valid) - 1)
            reasons = [
                f"Темп роста обводнённости замедляется: в первой половине периода "
                f"~{rate_first:+.2f} п.п./мес, во второй — ~{rate_second:+.2f} п.п./мес — "
                "форма кривой характерна для конусообразования; РИР в этом случае не "
                "показан — конус лечится сменой режима отбора, а не изоляцией интервала"
            ]
            return DiagnosticResult(
                WaterMechanism.CONING, 0.65, reasons, wor_raw, wor_prime, notes,
                productivity=productivity,
            )

    reasons = [
        f"Обводнённость не показывает выраженного продолжительного роста или скачков "
        f"за период наблюдения (от {watercut_series[0]:.1f}% до {watercut_series[-1]:.1f}%)"
    ]
    return DiagnosticResult(
        WaterMechanism.STABLE, 0.5, reasons, wor_raw, wor_prime, notes,
        productivity=productivity,
    )
