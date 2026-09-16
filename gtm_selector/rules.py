"""Правила (экспертные критерии) подбора ГТМ по скважине.

Каждая функция ``check_*`` анализирует параметры скважины и пороговые
значения из :class:`~gtm_selector.params.Thresholds` и возвращает
:class:`~gtm_selector.models.Candidate` — сработало правило или нет,
с расшифровкой причин и оценкой ожидаемого прироста дебита нефти.
"""

from __future__ import annotations

from .models import Well, WellStatus, GtmType, Candidate
from .params import Thresholds


def _scaled_uplift(qo: float, base_pct: float, factor: float) -> float:
    factor = max(0.0, min(factor, 1.5))
    return qo * (base_pct / 100.0) * factor


def check_opz(well: Well, t: Thresholds) -> Candidate:
    reasons = []
    matched = well.status == WellStatus.ACTIVE and well.skin >= t.opz_skin_min
    delta = 0.0
    if matched:
        reasons.append(
            f"Скин-фактор {well.skin:.1f} ≥ порога {t.opz_skin_min:.1f} — "
            "признак загрязнения ПЗП"
        )
        factor = well.skin / t.opz_skin_ref if t.opz_skin_ref else 1.0
        delta = _scaled_uplift(well.qo, t.opz_uplift_pct, factor)
    return Candidate(GtmType.OPZ, matched, reasons, delta)


def check_grp(well: Well, t: Thresholds) -> Candidate:
    reasons = []
    ok_perm = 0 < well.perm <= t.grp_perm_max
    ok_watercut = well.watercut <= t.grp_watercut_max
    ok_depletion = well.depletion <= t.grp_depletion_max
    ok_status = well.status == WellStatus.ACTIVE
    matched = ok_status and ok_perm and ok_watercut and ok_depletion
    delta = 0.0
    if matched:
        reasons.append(f"Проницаемость {well.perm:.1f} мД ≤ {t.grp_perm_max:.1f} мД (низкопроницаемый пласт)")
        reasons.append(f"Обводнённость {well.watercut:.1f}% ≤ {t.grp_watercut_max:.1f}%")
        reasons.append(f"Выработка запасов {well.depletion:.1f}% ≤ {t.grp_depletion_max:.1f}%")
        delta = well.qo * (t.grp_uplift_pct / 100.0)
    return Candidate(GtmType.GRP, matched, reasons, delta)


def check_rir(well: Well, t: Thresholds) -> Candidate:
    reasons = []
    matched = (
        well.status == WellStatus.ACTIVE
        and well.watercut >= t.rir_watercut_min
        and well.depletion <= t.rir_depletion_max
    )
    delta = 0.0
    if matched:
        reasons.append(f"Обводнённость {well.watercut:.1f}% ≥ {t.rir_watercut_min:.1f}% — прорыв воды")
        reasons.append(f"Выработка запасов {well.depletion:.1f}% ≤ {t.rir_depletion_max:.1f}% — есть смысл изолировать")
        delta = well.qo * (t.rir_uplift_pct / 100.0)
    return Candidate(GtmType.RIR, matched, reasons, delta)


def check_zbs(well: Well, t: Thresholds) -> Candidate:
    reasons = []
    matched = (
        well.watercut >= t.zbs_watercut_min
        and well.reserves_remaining >= t.zbs_reserves_min
    )
    delta = 0.0
    if matched:
        reasons.append(f"Обводнённость {well.watercut:.1f}% ≥ {t.zbs_watercut_min:.1f}% — эксплуатация неэффективна")
        reasons.append(
            f"Остаточные запасы {well.reserves_remaining:.1f} тыс.т ≥ {t.zbs_reserves_min:.1f} тыс.т — "
            "есть невыработанные запасы для нового ствола"
        )
        base_qo = well.qo if well.qo > 0 else well.last_active_qo
        delta = base_qo * (t.zbs_uplift_pct / 100.0)
    return Candidate(GtmType.ZBS, matched, reasons, delta)


def check_pump(well: Well, t: Thresholds) -> Candidate | None:
    """Возвращает кандидата на смену насоса (вверх или вниз) либо None."""
    util = well.pump_utilization
    if util is None or well.status != WellStatus.ACTIVE:
        return None
    if util >= t.pump_util_high:
        reasons = [
            f"Загрузка насоса {util * 100:.0f}% ≥ {t.pump_util_high * 100:.0f}% — "
            "текущий насос не обеспечивает потенциальный отбор жидкости"
        ]
        delta = well.qo * (t.pump_uplift_pct / 100.0)
        return Candidate(GtmType.PUMP_UP, True, reasons, delta)
    if util <= t.pump_util_low:
        reasons = [
            f"Загрузка насоса {util * 100:.0f}% ≤ {t.pump_util_low * 100:.0f}% — "
            "насос завышен по производительности, повышенный износ/энергозатраты"
        ]
        delta = well.qo * (t.pump_uplift_pct / 100.0) * 0.5
        return Candidate(GtmType.PUMP_DOWN, True, reasons, delta)
    return Candidate(GtmType.PUMP_UP, False, [], 0.0)


def check_perforation(well: Well, t: Thresholds) -> Candidate:
    reasons = []
    frac = well.unperforated_fraction
    matched = (
        well.status == WellStatus.ACTIVE
        and frac >= t.perf_unopened_min
        and well.reserves_remaining >= t.perf_reserves_min
    )
    delta = 0.0
    if matched:
        reasons.append(
            f"Невскрыта перфорацией {frac * 100:.0f}% н/нас. толщины (≥ {t.perf_unopened_min * 100:.0f}%)"
        )
        reasons.append(f"Остаточные запасы {well.reserves_remaining:.1f} тыс.т ≥ {t.perf_reserves_min:.1f} тыс.т")
        delta = well.qo * frac * (t.perf_uplift_pct / 100.0)
    return Candidate(GtmType.PERFORATION, matched, reasons, delta)


def check_reactivation(well: Well, t: Thresholds) -> Candidate:
    reasons = []
    matched = (
        well.status == WellStatus.IDLE
        and well.idle_days <= t.reactivation_max_idle_days
        and well.reserves_remaining >= t.reactivation_reserves_min
        and well.last_active_qo > 0
    )
    delta = 0.0
    if matched:
        reasons.append(f"Скважина в бездействии {well.idle_days} сут (≤ {t.reactivation_max_idle_days} сут)")
        reasons.append(
            f"Остаточные запасы {well.reserves_remaining:.1f} тыс.т ≥ {t.reactivation_reserves_min:.1f} тыс.т"
        )
        decline = (well.idle_days / 100.0) * (t.reactivation_decline_per_100days / 100.0)
        decline = max(0.0, min(decline, 0.9))
        delta = well.last_active_qo * (1.0 - decline)
        reasons.append(f"Ожидаемый дебит при запуске с учётом простоя: {delta:.1f} т/сут")
    return Candidate(GtmType.REACTIVATION, matched, reasons, delta)


ALL_CHECKS = [
    check_opz,
    check_grp,
    check_rir,
    check_zbs,
    check_perforation,
    check_reactivation,
]


def evaluate_well(well: Well, thresholds: Thresholds) -> list[Candidate]:
    """Возвращает список сработавших кандидатов ГТМ по скважине."""
    candidates: list[Candidate] = []

    if well.months_since_last_gtm < thresholds.min_months_between_gtm:
        return candidates  # слишком рано после предыдущего ГТМ

    for check in ALL_CHECKS:
        c = check(well, thresholds)
        if c is not None and c.matched:
            candidates.append(c)

    pump_candidate = check_pump(well, thresholds)
    if pump_candidate is not None and pump_candidate.matched:
        candidates.append(pump_candidate)

    return candidates
