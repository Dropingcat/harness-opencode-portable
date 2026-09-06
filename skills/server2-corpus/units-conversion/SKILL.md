---
name: units-conversion
description: Convert between physical units — energy (eV↔J↔kJ/mol↔kcal/mol), temperature (K↔°C), pressure (GPa↔MPa↔kgf/mm²), length (nm↔Å↔μm), angle (rad↔deg), time, velocity. Use our units.py for materials science units + pint for general. Use before any numeric comparison or physics computation.
category: physics
tags: [Units, Conversion, Energy, Temperature, Pressure, Length, Materials Science, pint]
dependencies: ["numpy", "pint"]
---

# Units Conversion

## Overview

Единый skill для конвертации физических единиц, используемый **всеми агентами** перед любым числовым сравнением или физическим расчётом. Гибрид двух движков:

1. **Наш `units.py`** (`/home/orangepi/projects/claimeai-service/scripts/units.py`) — заточен под **материаловедение**: твёрдость (HV/GPa/кгс/мм²), энергия на моль (eV/atom↔kJ/mol), температура (K↔°C), длина (nm/Å/μm), диффузия (см²/с), угол (rad/deg). Быстрый, детерминированный, без внешних зависимостей.
2. **pint** (OpenScience `dimensional-analysis`) — для **общих** единиц, которых нет в нашем registry (любые SI, производные, единицы из текста).

**Fallback chain:** сначала `units.py` (если единица в нашем registry) → иначе pint. Это гарантирует, что материаловедческие единицы конвертируются нашим детерминированным кодом, а всё остальное — pint.

## When to Use

Активировать **всегда** перед:
- числовым сравнением claim↔source (fact-checker, numeric_comparator);
- подстановкой значений в формулы (Arrhenius, ΔG, Scherrer, Williamson-Hall);
- проверкой размерностей (eV vs K — разные dimensions);
- конвертацией единиц из научного текста (кДж/моль, эВ/атом, ГПа, кгс/мм², нм, Å, °C).

**Правило:** если в тексте есть число с единицей и его нужно сравнить/подставить — сначала `units.convert()`, никогда не сравнивай числа с разными единицами напрямую.

## Core Workflows

### 1. Materials science units (our units.py)

Импорт и базовый вызов:

```python
import sys
sys.path.insert(0, "/home/orangepi/projects/claimeai-service/scripts")
import units

# 80 кДж/моль → эВ/атом (1 эВ/атом = 96.485 кДж/моль)
print(units.convert(80, "kj_per_mol", "ev_per_atom"))   # 0.8291
# 5 ГПа → кгс/мм² (1 ГПа = 10197 кгс/мм²... точнее 1 ГПа = 101.97 кгс/мм²)
print(units.convert(5, "gpa", "kgf_per_mm2"))           # 509.86
# 298 K → °C (аффинная, offset учтён)
print(units.convert(298, "kelvin", "celsius"))           # 24.85
# 1 нм → Å
print(units.convert(1, "nm", "angstrom"))               # 10.0
# 180° → рад
print(units.convert(180, "deg", "rad"))                  # 3.14159
```

**Поддерживаемые канонические единицы (`_CANON`):**

| Категория | Единицы |
|---|---|
| Твёрдость/давление | `hv`, `gpa`, `kpa`, `mpa`, `kgf`, `kgf_per_mm2` |
| Температура | `celsius`, `kelvin` |
| Энергия на моль | `kj_per_mol`, `ev_per_atom` |
| Длина | `um`, `nm`, `mm`, `cm`, `m`, `angstrom` |
| Диффузия | `cm2_per_s`, `m2_per_s`, `m_minus2` |
| Время | `min`, `hour` |
| Мощность | `watt`, `kW` |
| Угол | `rad`, `deg` |
| Сила | `N` |
| Безразмерные | `percent`, `ratio` |

**Алиасы (`_ALIASES`)** — принимает русские и латинские варианты: `GPa`, `MPa`, `кгс/мм²`, `°C`, `K`, `кДж/моль`, `эВ/атом`, `μm`, `нм`, `Å`, `см²/с`, `м⁻²`, `Вт`, `кВт`, `рад`, `%`, `раз` и др. `normalize_unit()` приводит любой алиас к канону.

### 2. General units (pint)

Для единиц, которых нет в нашем registry (любые SI, производные, экзотика):

```python
import pint
ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

# Конвертация любых единиц
E = Q_(80, 'kJ/mol')
print(E.to('eV/atom'))          # pint умеет (через mol/atom)
print(Q_(5, 'GPa').to('MPa'))   # 5000 MPa
print(Q_(1, 'nm').to('angstrom'))  # 10 Å

# DimensionalityError — разные размерности
try:
    bad = Q_(1, 'eV') + Q_(1, 'K')   # энергия + температура
except pint.DimensionalityError as e:
    print("DimensionalityError:", e)
```

**Fallback-функция (рекомендуемый паттерн):**

```python
import sys
sys.path.insert(0, "/home/orangepi/projects/claimeai-service/scripts")
import units
import pint

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

def convert_any(value, from_unit, to_unit):
    """units.py first, pint fallback."""
    try:
        return units.convert(value, from_unit, to_unit)
    except ValueError:
        return Q_(value, from_unit).to(to_unit).magnitude

# Примеры
print(convert_any(80, "kj_per_mol", "ev_per_atom"))  # 0.8291 (наш units.py)
print(convert_any(1, "m", "ft"))                     # 3.2808 (pint)
```

### 3. Energy conversions

**Критическая таблица (запомнить):**

| Соотношение | Множитель |
|---|---|
| 1 eV | 1.602e-19 J |
| 1 eV/atom | 96.485 kJ/mol |
| 1 eV/atom | 23.06 kcal/mol |
| 1 kJ | 0.239 kcal |
| 1 cal | 4.184 J |
| 1 kJ/mol | 0.01036 eV/atom |

```python
import sys
sys.path.insert(0, "/home/orangepi/projects/claimeai-service/scripts")
import units

# per-atom ↔ per-mole: 1 эВ/атом = 96.485 кДж/моль
print(units.convert(0.8, "ev_per_atom", "kj_per_mol"))  # 77.19
print(units.convert(77.19, "kj_per_mol", "ev_per_atom"))  # 0.8

# eV ↔ J (через pint, т.к. J нет в units.py)
import pint
ureg = pint.UnitRegistry()
print(ureg.Quantity(1, 'eV').to('J'))   # 1.602e-19 J
```

**Per-atom vs per-mole (Avogadro):** 1 эВ/атом = 1.602e-19 J × 6.022e23 /моль = 96.485 кДж/моль. **Никогда не путай** «эВ» (на атом) с «кДж/моль» (на моль) — разница в 96.485 раз. Если в тексте «0.8 эВ» и «77 кДж/моль» — это **одно и то же** (0.8 × 96.485 = 77.19).

### 4. Temperature

**Аффинная, НЕ линейная конверсия** — нельзя умножать/делить как ratio:

```
K = °C + 273.15
°C = K - 273.15
°F = °C × 9/5 + 32
°C = (°F - 32) × 5/9
```

```python
import sys
sys.path.insert(0, "/home/orangepi/projects/claimeai-service/scripts")
import units

print(units.convert(25, "celsius", "kelvin"))   # 298.15
print(units.convert(1273, "kelvin", "celsius")) # 999.85
```

**Критично:** `°C × 2 ≠ 2 × (температура в °C)`. Удвоение температуры имеет смысл только в **Кельвинах** (абсолютная шкала). «Вдвое горячее 100°C» = 2 × 373.15 K = 746.3 K = 473.15°C, **не** 200°C. Абсолютный ноль = 0 K = -273.15°C.

**Всегда** приводи T к Кельвину перед подстановкой в exp/ln (Arrhenius, ΔG, диффузия).

### 5. Dimension check

Проверка размерности — детектор несовместимых сравнений:

```python
import sys
sys.path.insert(0, "/home/orangepi/projects/claimeai-service/scripts")
import units

# Одинаковая размерность → конвертируемо
assert units.dimension("ev_per_atom") == units.dimension("kj_per_mol")  # оба — энергия
assert units.dimension("gpa") == units.dimension("kgf_per_mm2")          # оба — давление
assert units.dimension("nm") == units.dimension("angstrom")             # оба — длина

# Разная размерность → НЕ конвертируемо (eV vs K)
print(units.dimension("ev_per_atom"))  # (0,0,1,0,0,0,0,0,0) — энергия
print(units.dimension("kelvin"))       # (0,1,0,0,0,0,0,0,0) — температура
# units.convert(1, "ev_per_atom", "kelvin") → ValueError("unsupported conversion")
```

**pint-эквивалент:** `Q_(1,'eV').dimensionality != Q_(1,'K').dimensionality` → `DimensionalityError`.

**Правило:** если `dimension(from) != dimension(to)` — это **не конвертация**, а ошибка сравнения. Клайм «энергия 0.8 эВ при температуре 300 K» — разные величины, сравнивать нельзя.

## Conversion Factors Table (критично)

| Пара | Множитель |
|---|---|
| eV → J | 1.602e-19 |
| eV/atom → kJ/mol | 96.485 |
| eV/atom → kcal/mol | 23.06 |
| kJ → kcal | 0.239 |
| cal → J | 4.184 |
| GPa → kgf/mm² | 101.97 |
| GPa → MPa | 1000 |
| MPa → kgf/mm² | 9.80665 |
| rad → deg | 57.296 |
| nm → Å | 10 |
| μm → nm | 1000 |
| 1 Å | 1e-10 m |
| 1 eV | 1.602e-19 J |

## Common Pitfalls

1. **Per-atom vs per-mole (Avogadro 6.022e23)** — «эВ» (на атом) ≠ «кДж/моль» (на моль). Разница ×96.485. «0.8 эВ» = «77 кДж/моль». Никогда не сравнивай напрямую.
2. **Температура — не ratio** — `°C × 2` бессмысленно. Удвоение только в Кельвинах. `units.convert` учитывает offset (аффинная), но умножение/деление температур — ошибка.
3. **Dimension mismatch (eV vs K)** — энергия и температура — разные размерности. `units.convert` бросит `ValueError`, pint — `DimensionalityError`. Это сигнал «нельзя сравнивать», а не «нужна другая конверсия».
4. **Твёрдость HV vs давление GPa** — HV (Vickers) и GPa — **разные физические величины** (твёрдость vs давление), хотя в units.py у них одинаковая размерность-кортеж. Конвертация HV↔GPa в units.py использует эмпирический коэффициент 0.009807 (приближённый, для стали). Не путай с точным давлением.
5. **кгс/мм² vs МПа** — 1 кгс/мм² = 9.80665 МПа (не 10). units.py учитывает точно.
6. **°C в Arrhenius** — подставлять только Кельвин. `exp(-Ea/(R·T))` с T=570 вместо 843K даст абсурд.
7. **kcal/mol отсутствует в units.py** — для kcal/mol используй pint или конвертируй через kJ (1 kcal = 4.184 kJ). При необходимости добавь `kcal_per_mol` в registry.

## Integration with our tools

- **`numeric_comparator.py`** — использует `units.py` для приведения claim и source к общим единицам перед сравнением. Этот skill — источник правил конвертации для него.
- **`dimensional-analysis` skill** (`~/.config/opencode/skills/dimensional-analysis/`) — pint для общих единиц, Buckingham Pi, проверка размерностной согласованности формул. Используй его для производных величин, которых нет в units.py.
- **`thermodynamics` skill** — энергия (eV↔kJ/mol↔kcal/mol), температура (K↔°C). Всегда конвертируй через `units.convert` перед подстановкой в Arrhenius/ΔG.
- **`xrd-interpretation` skill** — длина (nm↔Å), угол (rad↔deg) для Bragg/Scherrer/Williamson-Hall. `units.convert(1, "nm", "angstrom")` = 10.

## CLI Example

```bash
# Быстрая конвертация без написания скрипта
python3 -c "import sys; sys.path.insert(0,'/home/orangepi/projects/claimeai-service/scripts'); from units import convert; print(convert(80, 'kj_per_mol', 'ev_per_atom'))"
# → 0.8291444265948076

# Dimension check
python3 -c "import sys; sys.path.insert(0,'/home/orangepi/projects/claimeai-service/scripts'); from units import dimension; print(dimension('ev_per_atom')==dimension('kj_per_mol'))"
# → True
```

## Usage Example (fact-check)

```python
import sys
sys.path.insert(0, '/home/orangepi/projects/claimeai-service/scripts')
from units import convert, dimension

# Клайм: "энергия активации 0.8 эВ (77 кДж/моль)"
eV = 0.8
kj = convert(eV, "ev_per_atom", "kj_per_mol")   # 77.19
assert abs(kj - 77) < 2.5                        # согласовано
assert dimension("ev_per_atom") == dimension("kj_per_mol")  # оба — энергия
# → единицы согласованы, клайм численно consistent
```
