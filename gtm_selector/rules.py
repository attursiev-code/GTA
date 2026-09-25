"""Правила (экспертные критерии) подбора ГТМ по скважине.

Каждая функция ``check_*`` анализирует параметры скважины и пороговые
значения из :class:`~gtm_selector.params.Thresholds` и возвращает
:class:`~gtm_selector.models.Candidate` — сработало правило или нет,
с расшифровкой причин и оценкой ожидаемого прироста дебита нефти.
"""

from __future__ import annotations

from .diagnostics import WaterMechanism, classify_water_mechanism
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


_RIR_MECHANISM_MAP = {
    # изолированный прорыв воды у забоя -> сквозная заливка (тампонирование)
    WaterMechanism.NEAR_WELLBORE: (GtmType.RIR_SQUEEZE, "rir_squeeze_uplift_pct"),
    # заколонный переток по промытому каналу -> селективная изоляция пропластка
    WaterMechanism.CHANNELING: (GtmType.RIR_SELECTIVE, "rir_selective_uplift_pct"),
    # неравномерная выработка нескольких пропластков -> перевод на другие интервалы
    WaterMechanism.MULTILAYER: (GtmType.RIR_INTERVAL_SWITCH, "rir_interval_switch_uplift_pct"),
}

_MECHANISM_LABELS = {
    WaterMechanism.NEAR_WELLBORE: "Заколонный переток",
    WaterMechanism.CHANNELING: "Прорыв по промытому интервалу",
    WaterMechanism.CONING: "Конусообразование",
    WaterMechanism.MULTILAYER: "Многослойный переток",
    WaterMechanism.STABLE: "Стабильна",
    WaterMechanism.INSUFFICIENT_DATA: "Недостаточно данных",
}


def check_rir(well: Well, t: Thresholds) -> Candidate:
    """Проверяет пороги обводнённости/выработки, затем диагностирует механизм
    обводнения по методу Chan и подбирает подходящий подтип РИР.

    Если диагностированный механизм — CONING, STABLE или INSUFFICIENT_DATA,
    кандидат РИР не рекомендуется (``matched=False``), но диагностика (механизм,
    обоснование, технические детали) всё равно возвращается — вызывающая сторона
    (``evaluate_well``) сохраняет такие попытки диагностики в общем списке, чтобы
    явно показать пользователю, что РИР был рассмотрен, но не рекомендован
    (конус лечится сменой режима, а не изоляцией; стабильная обводнённость и
    недостаток данных не дают оснований для РИР).
    """
    no_diagnosis = Candidate(GtmType.RIR_SQUEEZE, False, [], 0.0)

    if well.status != WellStatus.ACTIVE:
        return no_diagnosis
    if well.watercut < t.rir_watercut_min:
        return no_diagnosis
    if well.depletion > t.rir_depletion_max:
        return no_diagnosis

    diag = classify_water_mechanism(
        well.history,
        min_points=t.rir_min_history_points,
        spike_ratio=t.rir_spike_ratio,
    )
    mechanism_label = _MECHANISM_LABELS.get(diag.mechanism, diag.mechanism.value)

    threshold_reasons = [
        f"Обводнённость {well.watercut:.1f}% ≥ {t.rir_watercut_min:.1f}% — прорыв воды",
        f"Выработка запасов {well.depletion:.1f}% ≤ {t.rir_depletion_max:.1f}% — есть смысл изолировать",
    ]
    reasons = [*threshold_reasons, *diag.reasons]
    # Подтверждающий признак (не отдельный диагноз): значимое падение
    # продуктивности усиливает уверенность в поставленном диагнозе.
    if diag.productivity and diag.productivity.get("significant"):
        reasons.append(diag.productivity["note"])

    # Геологический контекст по ГИС/керну (не влияет на диагноз, только
    # поясняет его) — добавляется, только если данные по скважине заполнены.
    if well.log_water_saturation is not None:
        # TODO: порог 35% для "переходной зоны" условный, уточнить по факту.
        zone = "ближе к переходной зоне" if well.log_water_saturation >= 35.0 else "преимущественно нефтяным"
        reasons.append(
            f"Начальная водонасыщенность интервала перфорации по ГИС: "
            f"{well.log_water_saturation:.0f}% — интервал изначально был {zone}"
        )
    if well.log_permeability is not None:
        reasons.append(
            f"Проницаемость по керну в интервале перфорации: {well.log_permeability:.1f} мД"
        )

    mapping = _RIR_MECHANISM_MAP.get(diag.mechanism)
    if mapping is None:
        return Candidate(
            GtmType.RIR_SQUEEZE, False, reasons, 0.0,
            mechanism=mechanism_label, notes=list(diag.notes),
        )

    gtm_type, uplift_attr = mapping
    delta = well.qo * (getattr(t, uplift_attr) / 100.0)
    return Candidate(
        gtm_type, True, reasons, delta,
        mechanism=mechanism_label, notes=list(diag.notes),
    )


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


# Временно сфокусировано только на РИР — остальные проверки пока не
# используются в evaluate_well, но их код сохранён для последующего возврата.
ALL_CHECKS = []


def evaluate_well(well: Well, thresholds: Thresholds) -> list[Candidate]:
    """Возвращает список сработавших кандидатов ГТМ по скважине."""
    candidates: list[Candidate] = []

    if well.months_since_last_gtm < thresholds.min_months_between_gtm:
        return candidates  # слишком рано после предыдущего ГТМ

    for check in ALL_CHECKS:
        c = check(well, thresholds)
        if c is not None and c.matched:
            candidates.append(c)

    rir_candidate = check_rir(well, thresholds)
    # Включаем и рекомендованные, и явно не рекомендованные (но диагностированные)
    # случаи РИР — признак диагностики есть, только если был установлен mechanism.
    if rir_candidate is not None and (rir_candidate.matched or rir_candidate.mechanism):
        candidates.append(rir_candidate)

    return candidates
