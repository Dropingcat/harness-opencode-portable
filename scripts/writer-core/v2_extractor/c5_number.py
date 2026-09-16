"""C5-NUMBER collector — extract quantities (value + unit + dimension) from sentences.

Deterministic regex-based, no LLM. From docs/27_GRAPH_COLLECTORS.md graph 5.
Numbers feed into artifact_symbol graph.

Supports:
- decimal values: 12,5 / 12.5 / 0,25
- ranges: 20-30 / 0.5–0.7 / 10...100
- units: %, °C, мм, мкм, МПа, кг, г/м², л/м², МДж/м², с, ч, ГПа, Н/мм² ...
- dimensional suffixes
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# -------- unit lexicon (RU academic) --------
_UNIT_PATTERNS = {
    "percent": r"%|проц",
    "temp_c": r"[°оС]С",
    "temp_k": r"\bК\b",
    "micrometer": r"мкм|микрометр",
    "millimeter": r"мм",
    "centimeter": r"см",
    "meter": r"\bм\b",
    "nanometer": r"нм",
    "angstrom": r"[ÅÅӐA]",
    "mpa": r"МПа",
    "gpa": r"ГПа",
    "kg": r"кг",
    "gram": r"\bг\b",
    "kg_per_ha": r"кг/га",
    "mg_per_m2h": r"мг/м2ч|мг/м²ч",
    "g_per_m2": r"г/м²|г/м2",
    "l_per_m2": r"л/м²|л/м2",
    "mega_joule_m2": r"МДж/м²|МДж/м2",
    "second": r"\bс\b",
    "hour": r"\bч\.?\b",
    "minute": r"\bмин\b",
    "herz": r"Гц",
}


@dataclass(frozen=True, slots=True)
class Quantity:
    id: str
    value_lower: float | None
    value_upper: float | None
    value_exact: float | None
    unit: str | None
    dimension: str | None
    raw: str
    sentence_index: int
    position: int
    original: str


_NUM = r"(?:\d+[.,]\d+|\d+)(?:\s*[–—\-]\s*\d+[.,]?\d*)?"
# Единица: буквы/цифры/спецсимволы; НЕ захватывает после пробела новое слово.
# Расширено: включает "мг/м2ч", "МДж/м2", "г/м2".
_UNIT_CLASS = r"[°оССa-zA-Zа-яА-ЯёЁ/%²№\d]+"
_NUMBER_RE = re.compile(
    r"(" + _NUM + r")\s*"
    r"(" + _UNIT_CLASS + r")"
    r"(?![а-яёa-zA-Z])",   # stop при переходе в обычное слово (не единица)
    re.UNICODE,
)


def _norm_num(s: str) -> float:
    s = s.replace(",", ".").strip()
    return float(s)


def _split_range(raw: str) -> tuple[float | None, float | None, float | None]:
    parts = re.split(r"[–—\-]", raw.replace(",", ".").strip())
    if len(parts) == 2:
        try:
            return float(parts[0]), float(parts[1]), None
        except ValueError:
            pass
    try:
        v = float(raw.replace(",", "."))
        return v, v, v
    except ValueError:
        return None, None, None


def extract_quantities(sentences: list[str]) -> list[Quantity]:
    out: list[Quantity] = []
    qid = 0
    for si, sent in enumerate(sentences):
        for m in _NUMBER_RE.finditer(sent):
            num_raw = m.group(1)
            unit_raw = m.group(2).strip()
            if not unit_raw:
                continue
            lo, hi, exact = _split_range(num_raw)
            unit, dim = _resolve_unit(unit_raw)
            if unit is None:
                continue
            out.append(
                Quantity(
                    id=f"QTY_BLK_{qid:05d}",
                    value_lower=lo,
                    value_upper=hi,
                    value_exact=exact,
                    unit=unit,
                    dimension=dim,
                    raw=num_raw + unit_raw,
                    sentence_index=si,
                    position=m.start(),
                    original=num_raw,
                )
            )
            qid += 1
    return out


def _resolve_unit(raw: str) -> tuple[str | None, str | None]:
    """Map raw unit token to (unit, dimension)."""
    r = raw.strip().lower()
    # try longest/most specific first
    if re.match(r"мг/м2ч|мг/м²ч", r): return "мг/м2ч", "corrosion_rate"
    for a, b in [
        (r"\bкг/га\b", "кг/га"),
        (r"г/м²|г/м2", "г/м2"),
        (r"л/м²|л/м2", "л/м2"),
        (r"МДж/м²|МДж/м2", "МДж/м2"),
    ]:
        if re.match(a, r):
            if "га" in r: return "кг/га", "density"
            return "г/м2" if "/м" in r and "МДж" not in r else r, "per_area"
    if re.search(r"мкм", r): return "мкм", "length"
    if re.search(r"нм", r): return "нм", "length"
    if re.search(r"мм", r): return "мм", "length"
    if re.search(r"см", r): return "см", "length"
    if re.search(r"мпа", r): return "МПа", "stress"
    if re.search(r"гпа", r): return "ГПа", "stress"
    if re.search(r"%", r): return "%", "ratio"
    if re.search(r"°с|оС|ос", r): return "°C", "temperature"
    if re.search(r"\bкг\b", r): return "кг", "mass"
    if re.search(r"\bг\b", r): return "г", "mass"
    if re.search(r"мдж/м", r): return "МДж/м2", "energy_density"
    if re.search(r"\bс\b", r): return "с", "time"
    if re.search(r"\bч\b", r): return "ч", "time"
    return None, None


def extract_from_sentences(sentences: list[str]) -> list[dict]:
    qs = extract_quantities(sentences)
    return [
        {
            "id": q.id,
            "value_lower": q.value_lower,
            "value_upper": q.value_upper,
            "unit": q.unit,
            "dimension": q.dimension,
            "raw": q.raw,
            "sentence_index": q.sentence_index,
        }
        for q in qs
    ]