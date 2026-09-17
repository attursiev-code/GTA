"""Модели данных: скважина, тип ГТМ, кандидат, рекомендация."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum


class WellStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"

    @property
    def label(self) -> str:
        return {"active": "Действующая", "idle": "Бездействующая"}[self.value]

    @classmethod
    def from_any(cls, value) -> "WellStatus":
        if isinstance(value, WellStatus):
            return value
        text = str(value).strip().lower()
        if text in ("active", "действующая", "работает", "1", "true"):
            return cls.ACTIVE
        return cls.IDLE


class GtmType(str, Enum):
    OPZ = "opz"
    GRP = "grp"
    RIR_SQUEEZE = "rir_squeeze"
    RIR_SELECTIVE = "rir_selective"
    RIR_INTERVAL_SWITCH = "rir_interval_switch"
    ZBS = "zbs"
    PUMP_UP = "pump_up"
    PUMP_DOWN = "pump_down"
    PERFORATION = "perforation"
    REACTIVATION = "reactivation"

    @property
    def label(self) -> str:
        return GTM_LABELS[self]


GTM_LABELS = {
    GtmType.OPZ: "ОПЗ (обработка призабойной зоны)",
    GtmType.GRP: "ГРП (гидроразрыв пласта)",
    GtmType.RIR_SQUEEZE: "РИР: сквозная заливка (тампонирование)",
    GtmType.RIR_SELECTIVE: "РИР: селективная изоляция пропластка",
    GtmType.RIR_INTERVAL_SWITCH: "РИР: перевод на другие интервалы",
    GtmType.ZBS: "ЗБС (зарезка бокового ствола)",
    GtmType.PUMP_UP: "Смена насоса (увеличение производительности)",
    GtmType.PUMP_DOWN: "Смена насоса (уменьшение производительности)",
    GtmType.PERFORATION: "Доперфорация пласта",
    GtmType.REACTIVATION: "Вывод из бездействия",
}


@dataclass
class ProductionPoint:
    """Точка истории добычи скважины: дата, дебит нефти и дебит воды."""

    date: str
    qo: float
    qw: float


@dataclass
class Well:
    """Данные по скважине, необходимые для подбора ГТМ."""

    id: str
    name: str
    formation: str = ""
    status: WellStatus = WellStatus.ACTIVE
    perforation_interval: str = ""  # интервал перфорации (как есть из базы)
    horizon: str = ""               # геологический горизонт (как есть из базы)

    qo: float = 0.0            # дебит нефти, т/сут
    ql: float = 0.0            # дебит жидкости, т/сут
    watercut: float = 0.0      # обводненность, %

    p_res: float = 0.0         # текущее пластовое давление, атм
    p_res_initial: float = 0.0  # начальное пластовое давление, атм
    p_wf: float = 0.0          # забойное давление, атм

    skin: float = 0.0          # скин-фактор
    perm: float = 0.0          # проницаемость, мД
    thickness_total: float = 0.0       # общая н/нас. толщина, м
    thickness_perforated: float = 0.0  # вскрытая перфорацией толщина, м

    reserves_remaining: float = 0.0  # остаточные извлекаемые запасы, тыс.т
    depletion: float = 0.0     # выработка запасов от НИЗ, %

    pump_capacity: float = 0.0  # номинальная производительность насоса, т/сут
    idle_days: int = 0          # простой скважины, сут (для бездействующих)
    last_active_qo: float = 0.0  # дебит нефти перед остановкой, т/сут
    months_since_last_gtm: int = 999  # месяцев с последнего ГТМ на скважине

    notes: str = ""
    history: list[ProductionPoint] = field(default_factory=list)

    def __post_init__(self):
        self.status = WellStatus.from_any(self.status)

    @property
    def unperforated_fraction(self) -> float:
        if self.thickness_total <= 0:
            return 0.0
        opened = min(self.thickness_perforated, self.thickness_total)
        return max(0.0, (self.thickness_total - opened) / self.thickness_total)

    @property
    def pump_utilization(self) -> float | None:
        if self.pump_capacity <= 0:
            return None
        return self.ql / self.pump_capacity

    @property
    def pressure_depletion_ratio(self) -> float | None:
        if self.p_res_initial <= 0:
            return None
        return max(0.0, (self.p_res_initial - self.p_res) / self.p_res_initial)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Well":
        data = dict(d)
        data["status"] = WellStatus.from_any(data.get("status", "active"))
        history = data.get("history")
        if history:
            data["history"] = [
                p if isinstance(p, ProductionPoint) else ProductionPoint(**p)
                for p in history
            ]
        allowed = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in data.items() if k in allowed}
        return cls(**data)


@dataclass
class Candidate:
    """Кандидат на проведение ГТМ по конкретной скважине с обоснованием."""

    gtm_type: GtmType
    matched: bool
    reasons: list[str] = field(default_factory=list)
    delta_qo: float = 0.0  # ожидаемый прирост дебита нефти, т/сут
    mechanism: str = ""    # диагностированный механизм обводнения (текстом), если применимо
    notes: list[str] = field(default_factory=list)  # технические детали диагностики


@dataclass
class Recommendation:
    """Итоговая рекомендация по ГТМ с экономической оценкой."""

    well_id: str
    well_name: str
    gtm_type: GtmType
    reasons: list[str]
    delta_qo: float           # т/сут, ожидаемый прирост
    incremental_production: float  # т, за период эффекта
    revenue: float            # руб.
    cost: float                # руб.
    economic_effect: float     # руб. = revenue - cost
    payback_months: float | None
    roi: float | None
    matched: bool = True   # False — РИР рассмотрен, но не рекомендован (механизм CONING/STABLE/INSUFFICIENT_DATA)
    mechanism: str = ""    # диагностированный механизм обводнения (текстом)
    notes: list[str] = field(default_factory=list)  # технические детали диагностики

    @property
    def gtm_label(self) -> str:
        if not self.matched:
            return "РИР не рекомендуется"
        return self.gtm_type.label
