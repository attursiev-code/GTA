"""Модели данных: скважина, тип ГТМ, кандидат, рекомендация."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from .params import Thresholds

GRP_STATUS_LABELS = {
    "unknown": "Нет данных",
    "no": "Не проводился",
    "yes": "Проводился",
}
GRP_STATUS_LABELS_REVERSE = {v: k for k, v in GRP_STATUS_LABELS.items()}


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
class GdisRecord:
    """Запись гидродинамического исследования скважины (ГДИС) из Excel-базы.

    Формат файла ГДИС может отличаться от базы к базе (разные месторождения/
    выгрузки) — импорт (см. gdis_io.py) ищет колонки по ключевым словам, а не
    по точному названию, и любое поле, для которого в файле не нашлось
    подходящей колонки, остаётся пустым/None — это нормальная ситуация, а не
    ошибка импорта.
    """

    well_id: str
    object_name: str = ""
    horizon: str = ""
    interval: str = ""
    date: str = ""              # ГГГГ-ММ-ДД; пусто, если распознать не удалось
    research_type: str = ""
    skin: float | None = None
    permeability: float | None = None
    quality: str = ""
    comment: str = ""


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

    # Петрофизика по ГИС/керну в интервале перфорации (импорт LAS, см. las_io.py)
    log_porosity: float | None = None           # пористость (PHIE), доли ед.
    log_water_saturation: float | None = None   # начальная водонасыщенность, %
    log_permeability: float | None = None        # проницаемость по керну, мД

    # Признак ГРП (ручной ввод, см. well_dialog.py)
    grp_status: str = "unknown"  # "unknown" | "no" | "yes"
    grp_date: str = ""           # дата ГРП, ГГГГ-ММ-ДД; пусто, если не проводился/неизвестно

    # Записи ГДИС (гидродинамические исследования), импорт из Excel-базы
    # (см. gdis_io.py) — формат листа может отличаться от базы к базе.
    gdis_records: list[GdisRecord] = field(default_factory=list)

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
        gdis_records = data.get("gdis_records")
        if gdis_records:
            data["gdis_records"] = [
                r if isinstance(r, GdisRecord) else GdisRecord(**r)
                for r in gdis_records
            ]
        allowed = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in data.items() if k in allowed}
        return cls(**data)


def watercut_level(value: float, thresholds: Thresholds) -> str:
    """Качественный уровень обводнённости по условным границам из Thresholds.

    Границы (``watercut_low_max``/``watercut_mid_max``) заданы пользователем
    в настройках — единого стандартного значения в источниках нет.
    """
    if value <= thresholds.watercut_low_max:
        return "низкая"
    if value <= thresholds.watercut_mid_max:
        return "средняя"
    return "высокая"


def gdis_matches_well_object(record: GdisRecord, well: Well) -> bool:
    """Проверяет, относится ли запись ГДИС к текущему объекту/горизонту скважины.

    Сравнение без учёта регистра/пробелов. Если объект/горизонт в записи не
    заполнены (в файле ГДИС не было такой колонки) — проверить нечем, запись
    считается относящейся к текущему объекту (не блокируем её).
    """
    object_filled = bool(record.object_name.strip())
    horizon_filled = bool(record.horizon.strip())
    if object_filled and record.object_name.strip().lower() != well.formation.strip().lower():
        return False
    if horizon_filled and record.horizon.strip().lower() != well.horizon.strip().lower():
        return False
    return True


def format_date_ddmmyyyy(iso_date: str) -> str:
    """Преобразует дату из ГГГГ-ММ-ДД в ДД.ММ.ГГГГ для отображения.

    Возвращает пустую строку, если ``iso_date`` пуст; если формат неожиданный —
    возвращает исходную строку как есть, не ломая отображение.
    """
    if not iso_date:
        return ""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso_date


@dataclass
class Candidate:
    """Кандидат на проведение ГТМ по конкретной скважине с обоснованием.

    Текущий поток подбора РИР — чисто диагностический, без экономики
    (см. ``engine.select_gtm``): ``Candidate`` заполняется полями
    ``well_id``/``well_name`` прямо там и используется как результат
    подбора напрямую, без промежуточного ``Recommendation``.
    """

    gtm_type: GtmType
    matched: bool
    reasons: list[str] = field(default_factory=list)
    delta_qo: float = 0.0  # ожидаемый прирост дебита нефти, т/сут
    mechanism: str = ""    # диагностированный механизм обводнения (текстом), если применимо
    notes: list[str] = field(default_factory=list)  # технические детали диагностики
    well_id: str = ""       # заполняется в engine.select_gtm
    well_name: str = ""     # заполняется в engine.select_gtm

    @property
    def gtm_label(self) -> str:
        if not self.matched:
            return "РИР не рекомендуется"
        return self.gtm_type.label


@dataclass
class Recommendation:
    """Итоговая рекомендация по ГТМ с экономической оценкой.

    Не используется в текущем потоке подбора РИР (там результат — это
    ``Candidate``, см. ``engine.select_gtm``) — класс сохранён для будущего
    возврата экономического блока (когда появятся актуальные цены).
    """

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
