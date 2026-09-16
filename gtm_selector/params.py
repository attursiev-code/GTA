"""Настраиваемые параметры: пороги для правил подбора и экономика."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Thresholds:
    """Пороговые значения критериев подбора ГТМ (можно менять в настройках)."""

    # ОПЗ — обработка призабойной зоны
    opz_skin_min: float = 3.0
    opz_uplift_pct: float = 25.0       # % прироста Qo при уверенном срабатывании
    opz_skin_ref: float = 10.0         # скин, при котором прирост = 100% от uplift_pct

    # ГРП — гидроразрыв пласта
    grp_perm_max: float = 15.0         # мД
    grp_watercut_max: float = 50.0     # %
    grp_depletion_max: float = 65.0    # %
    grp_uplift_pct: float = 80.0

    # РИР — ремонтно-изоляционные работы (диагностика механизма по методу Chan)
    rir_watercut_min: float = 60.0
    rir_depletion_max: float = 90.0
    rir_min_history_points: int = 6
    rir_spike_ratio: float = 8.0
    rir_squeeze_uplift_pct: float = 12.0
    rir_selective_uplift_pct: float = 18.0
    rir_interval_switch_uplift_pct: float = 25.0

    # ЗБС — зарезка бокового ствола
    zbs_watercut_min: float = 95.0
    zbs_reserves_min: float = 5.0      # тыс.т остаточных запасов
    zbs_uplift_pct: float = 200.0

    # Насосное оборудование
    pump_util_high: float = 0.9        # выше — насос недогружен по возможностям пласта (нужен более производительный)
    pump_util_low: float = 0.35        # ниже — насос избыточен (перегрев/лишние затраты)
    pump_uplift_pct: float = 10.0

    # Доперфорация
    perf_unopened_min: float = 0.15    # доля невскрытой толщины
    perf_reserves_min: float = 3.0     # тыс.т
    perf_uplift_pct: float = 30.0

    # Вывод из бездействия
    reactivation_max_idle_days: int = 720
    reactivation_reserves_min: float = 2.0
    reactivation_decline_per_100days: float = 5.0  # % потери потенциала на каждые 100 сут простоя

    # Общее
    min_months_between_gtm: int = 6    # не рекомендовать повторно раньше этого срока

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Thresholds":
        allowed = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in allowed})


@dataclass
class EconomicParams:
    """Экономические параметры для оценки эффекта от ГТМ."""

    oil_price: float = 35000.0     # руб./т, цена реализации нефти
    opex_per_ton: float = 12000.0  # руб./т, удельные операционные затраты

    effect_duration_months: int = 12   # период учёта эффекта
    monthly_decline_pct: float = 3.0   # темп падения доп. дебита, %/мес

    cost_by_type: dict = field(default_factory=lambda: {
        "opz": 1_500_000.0,
        "grp": 12_000_000.0,
        "rir_squeeze": 2_000_000.0,
        "rir_selective": 3_500_000.0,
        "rir_interval_switch": 6_000_000.0,
        "zbs": 45_000_000.0,
        "pump_up": 800_000.0,
        "pump_down": 600_000.0,
        "perforation": 2_500_000.0,
        "reactivation": 1_800_000.0,
    })

    @property
    def netback(self) -> float:
        return self.oil_price - self.opex_per_ton

    def cost_for(self, gtm_type) -> float:
        key = gtm_type.value if hasattr(gtm_type, "value") else str(gtm_type)
        return self.cost_by_type.get(key, 0.0)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EconomicParams":
        data = dict(d)
        cost_by_type = data.pop("cost_by_type", None)
        allowed = {f for f in cls.__dataclass_fields__}
        obj = cls(**{k: v for k, v in data.items() if k in allowed})
        if cost_by_type:
            obj.cost_by_type.update(cost_by_type)
        return obj


@dataclass
class Settings:
    thresholds: Thresholds = field(default_factory=Thresholds)
    economics: EconomicParams = field(default_factory=EconomicParams)

    def to_dict(self) -> dict:
        return {
            "thresholds": self.thresholds.to_dict(),
            "economics": self.economics.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        return cls(
            thresholds=Thresholds.from_dict(d.get("thresholds", {})),
            economics=EconomicParams.from_dict(d.get("economics", {})),
        )
