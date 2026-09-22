_CANON = {
    "hv": "hv",
    "gpa": "gpa",
    "kpa": "kpa",
    "mpa": "mpa",
    "kgf": "kgf",
    "kgf_per_mm2": "kgf_per_mm2",
    "celsius": "celsius",
    "kelvin": "kelvin",
    "kj_per_mol": "kj_per_mol",
    "ev_per_atom": "ev_per_atom",
    "um": "um",
    "nm": "nm",
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "angstrom": "angstrom",
    "cm2_per_s": "cm2_per_s",
    "m2_per_s": "m2_per_s",
    "m_minus2": "m_minus2",
    "min": "min",
    "hour": "hour",
    "watt": "watt",
    "kW": "kW",
    "rad": "rad",
    "deg": "deg",
    "N": "N",
    "percent": "percent",
    "ratio": "ratio",
}

_ALIASES = {
    "HV": "hv",
    "GPa": "gpa",
    "KPa": "kpa",
    "kPa": "kpa",
    "MPa": "mpa",
    "кгс": "kgf",
    "кгс/мм²": "kgf_per_mm2",
    "кгс/мм2": "kgf_per_mm2",
    "C": "celsius",
    "Celsius": "celsius",
    "°C": "celsius",
    "°c": "celsius",
    "K": "kelvin",
    "Kelvin": "kelvin",
    "°К": "kelvin",
    "kJ/mol": "kj_per_mol",
    "кДж/моль": "kj_per_mol",
    "kJ_per_mol": "kj_per_mol",
    "eV/atom": "ev_per_atom",
    "эВ/атом": "ev_per_atom",
    "eV_per_atom": "ev_per_atom",
    "um": "um",
    "umm": "um",
    "μm": "um",
    "µm": "um",
    "мкм": "um",
    "nm": "nm",
    "нм": "nm",
    "mm": "mm",
    "мм": "mm",
    "cm": "cm",
    "см": "cm",
    "m": "m",
    "м": "m",
    "Å": "angstrom",
    "ангстрем": "angstrom",
    "cm2/s": "cm2_per_s",
    "см²/с": "cm2_per_s",
    "см2/с": "cm2_per_s",
    "m2/s": "m2_per_s",
    "м²/с": "m2_per_s",
    "м-2": "m_minus2",
    "м⁻²": "m_minus2",
    "min": "min",
    "мин": "min",
    "минут": "min",
    "час": "hour",
    "часов": "hour",
    "hour": "hour",
    "ч": "hour",
    "h": "hour",
    "Вт": "watt",
    "W": "watt",
    "watt": "watt",
    "кВт": "kW",
    "kW": "kW",
    "рад": "rad",
    "rad": "rad",
    "°": "deg",
    "град": "deg",
    "Н": "N",
    "N": "N",
    "н": "N",
    "%": "percent",
    "раз": "ratio",
    "раза": "ratio",
    "times": "ratio",
}

# Семантическая размерность (величина, не просто ключ единицы).
# Кортежи уникальны на одну физическую величину => разность размерностей
# означает "нельзя сравнивать" (not_comparable), а не конвертацию.
_DIMENSION = {
    "hv": (1, 0, 0, 0, 0, 0, 0, 0, 0),
    "gpa": (1, 0, 0, 0, 0, 0, 0, 0, 0),
    "kpa": (1, 0, 0, 0, 0, 0, 0, 0, 0),
    "mpa": (1, 0, 0, 0, 0, 0, 0, 0, 0),
    "kgf": (1, 0, 0, 0, 0, 0, 0, 0, 0),
    "kgf_per_mm2": (1, 0, 0, 0, 0, 0, 0, 0, 0),
    "celsius": (0, 1, 0, 0, 0, 0, 0, 0, 0),
    "kelvin": (0, 1, 0, 0, 0, 0, 0, 0, 0),
    "kj_per_mol": (0, 0, 1, 0, 0, 0, 0, 0, 0),
    "ev_per_atom": (0, 0, 1, 0, 0, 0, 0, 0, 0),
    "um": (0, 0, 0, 1, 0, 0, 0, 0, 0),
    "nm": (0, 0, 0, 1, 0, 0, 0, 0, 0),
    "mm": (0, 0, 0, 1, 0, 0, 0, 0, 0),
    "cm": (0, 0, 0, 1, 0, 0, 0, 0, 0),
    "m": (0, 0, 0, 1, 0, 0, 0, 0, 0),
    "angstrom": (0, 0, 0, 1, 0, 0, 0, 0, 0),
    "cm2_per_s": (0, 0, 0, 0, 1, 0, 0, 0, 0),
    "m2_per_s": (0, 0, 0, 0, 1, 0, 0, 0, 0),
    "m_minus2": (0, 0, 0, 0, 1, 0, 0, 0, 0),
    "min": (0, 0, 0, 0, 0, 1, 0, 0, 0),
    "hour": (0, 0, 0, 0, 0, 1, 0, 0, 0),
    "watt": (0, 0, 0, 0, 0, 0, 1, 0, 0),
    "kW": (0, 0, 0, 0, 0, 0, 1, 0, 0),
    "rad": (0, 0, 0, 0, 0, 0, 0, 1, 0),
    "deg": (0, 0, 0, 0, 0, 0, 0, 1, 0),
    "N": (0, 0, 0, 0, 0, 0, 0, 0, 1),
    "percent": (0, 0, 0, 0, 0, 0, 0, 0, 0),
    "ratio": (0, 0, 0, 0, 0, 0, 0, 0, 0),
}

# Пересчёт в базовые единицы СИ (для конвертации внутри одной размерности).
_BASE = {
    "hv": 1.0,
    "gpa": 1e9, "kpa": 1e3, "mpa": 1e6, "kgf": 1e6 * 9.80665, "kgf_per_mm2": 1e6 * 9.80665,
    "celsius": 0.0, "kelvin": 0.0,
    "kj_per_mol": 1.0, "ev_per_atom": 1.0,
    "angstrom": 1e-10, "nm": 1e-9, "um": 1e-6, "mm": 1e-3, "cm": 1e-2, "m": 1.0,
    "cm2_per_s": 1e-4, "m2_per_s": 1.0, "m_minus2": 1.0,
    "min": 60.0, "hour": 3600.0,
    "watt": 1.0, "kW": 1e3,
    "rad": 1.0, "deg": 3.141592653589793 / 180.0,
    "N": 1.0, "percent": 1.0, "ratio": 1.0,
}

_TEMPERATURE = {"celsius", "kelvin"}


def normalize_unit(unit: str) -> str:
    if unit is None:
        raise ValueError("unsupported conversion")
    key = unit.strip()
    if key in _CANON:
        return _CANON[key]
    if key in _ALIASES:
        return _ALIASES[key]
    lower = key.lower()
    if lower in _CANON:
        return _CANON[lower]
    if lower in _ALIASES:
        return _ALIASES[lower]
    raise ValueError("unsupported conversion")


def dimension(unit: str) -> tuple:
    return _DIMENSION[normalize_unit(unit)]


def convert(value: float, from_unit: str, to_unit: str) -> float:
    f = normalize_unit(from_unit)
    t = normalize_unit(to_unit)
    if f == t:
        return value
    if dimension(f) != dimension(t):
        raise ValueError("unsupported conversion")
    # температура — аффинная, а не линейная
    if f in _TEMPERATURE and t in _TEMPERATURE:
        if f == "celsius":
            return value + 273.15 if t == "kelvin" else value
        return value - 273.15 if t == "celsius" else value
    # энергия на моль (eV/atom ↔ kJ/mol) и твёрдость/давление — фиксированные соотношения
    if {f, t} == {"kj_per_mol", "ev_per_atom"}:
        return value * (1 / 96.485) if f == "kj_per_mol" else value * 96.485
    if {f, t} == {"hv", "gpa"}:
        return value * 0.009807 if f == "hv" else value / 0.009807
    if {f, t} == {"kgf_per_mm2", "gpa"}:
        return value * 0.00980665 if f == "kgf_per_mm2" else value / 0.00980665
    if {f, t} == {"kgf_per_mm2", "mpa"}:
        return value * 9.80665 if f == "kgf_per_mm2" else value / 9.80665
    # давление
    if f in ("kpa", "mpa", "gpa", "kgf", "kgf_per_mm2") and t in ("kpa", "mpa", "gpa", "kgf", "kgf_per_mm2"):
        return value * _BASE[f] / _BASE[t]
    # длина / время / мощность / угол / диффузия — линейные через _BASE
    if f in _BASE and t in _BASE:
        return value * _BASE[f] / _BASE[t]
    raise ValueError("unsupported conversion")
