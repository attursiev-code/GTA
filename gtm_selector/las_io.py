"""Импорт данных ГИС/керна из LAS-файлов (формат LAS 2.0) и привязка к скважинам.

Минимальный парсер LAS 2.0: не претендует на полную поддержку спецификации,
разбирает только секции ``~CURVE``/``~CURVES`` (список кривых по порядку) и
``~ASCII``/``~A`` (собственно данные) — этого достаточно, чтобы вытащить
глубину и нужные петрофизические кривые.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Well


def parse_las(path: str | Path) -> tuple[list[str], list[list[float]]]:
    """Читает LAS 2.0. Возвращает (имена кривых по порядку, строки данных).

    Первая кривая — глубина (DEPT). Строки-комментарии (начинаются с '#')
    и пустые строки пропускаются; строки данных, которые не удаётся разобрать
    как числа, также пропускаются (не прерывают чтение файла).
    """
    curves: list[str] = []
    rows: list[list[float]] = []
    section: str | None = None

    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("~"):
            header = line[1:].strip().upper()
            if header.startswith("CURVE"):
                section = "curve"
            elif header.startswith("A"):
                section = "ascii"
            else:
                section = None
            continue

        if section == "curve":
            # Формат строки: "MNEM .UNIT   VALUE : Описание" — мнемоника кривой
            # идёт до первой точки.
            mnem = line.split(".")[0].strip()
            if mnem:
                curves.append(mnem)
        elif section == "ascii":
            parts = line.split()
            try:
                values = [float(p) for p in parts]
            except ValueError:
                continue
            rows.append(values)

    return curves, rows


def extract_petrophysics_at_intervals(
    curves: list[str],
    rows: list[list[float]],
    intervals: list[tuple[float, float]],
    null_value: float = -999.25,
) -> dict:
    """Усредняет петрофизические кривые по точкам внутри интервалов перфорации.

    Для кривых PHIE (пористость), SW (водонасыщенность), Perm_core
    (проницаемость по керну) — если есть в ``curves`` — считает среднее по
    точкам, чья глубина (первая кривая) попадает в любой из ``intervals``,
    исключая ``null_value`` и -9999.0.

    Водонасыщенность в LAS обычно хранится долей (0-1), а не процентом;
    результат нормализуется к процентам (0-100), чтобы соответствовать
    остальным полям проекта (``Well.watercut`` и т.п. — тоже в процентах).

    Возвращает {'porosity': float|None, 'water_saturation': float|None,
    'permeability': float|None} — None, если валидных точек нет.
    """
    if not curves:
        return {"porosity": None, "water_saturation": None, "permeability": None}

    depth_idx = 0
    curve_index = {name.strip().upper(): i for i, name in enumerate(curves)}
    mapping = {
        "porosity": curve_index.get("PHIE"),
        "water_saturation": curve_index.get("SW"),
        "permeability": curve_index.get("PERM_CORE"),
    }

    def is_null(value: float) -> bool:
        return abs(value - null_value) < 1e-6 or abs(value - (-9999.0)) < 1e-6

    def in_intervals(depth: float) -> bool:
        return any(top <= depth <= bottom for top, bottom in intervals)

    result: dict[str, float | None] = {}
    for key, col_idx in mapping.items():
        if col_idx is None:
            result[key] = None
            continue
        values = []
        for row in rows:
            if depth_idx >= len(row) or col_idx >= len(row):
                continue
            depth = row[depth_idx]
            value = row[col_idx]
            if not in_intervals(depth) or is_null(value):
                continue
            values.append(value)
        if not values:
            result[key] = None
            continue
        avg = sum(values) / len(values)
        result[key] = avg

    water_saturation = result.get("water_saturation")
    if water_saturation is not None and abs(water_saturation) <= 1.5:
        result["water_saturation"] = water_saturation * 100.0

    return result


def match_las_to_well(las_filename: str, wells: list[Well]) -> Well | None:
    """Сопоставляет LAS-файл со скважиной по числу в имени файла.

    Извлекает число из имени файла (например, '23' из '23.las', ведущие
    нули убираются) и ищет скважину, чьё имя или номер оканчивается на это
    число после дефиса ('У-23' на '23', 'УС-3' на '3'). Возвращает найденную
    скважину или ``None``.
    """
    stem = Path(las_filename).stem
    match = re.search(r"(\d+)", stem)
    if not match:
        return None

    number = str(int(match.group(1)))  # убираем ведущие нули
    suffix = f"-{number}"
    for well in wells:
        if well.name.endswith(suffix) or well.id.endswith(suffix):
            return well
    return None
