---
name: thermodynamics
description: Thermodynamics calculations and claim verification — enthalpy (ΔH), entropy (ΔS), Gibbs free energy (ΔG), activation energy (Ea), heat capacity (Cp, Debye model), thermal conductivity. Use for fact-checking thermo claims in scientific texts and for researcher computations, with strict unit handling via numeric_comparator (eV↔J↔kJ/mol↔kcal/mol, K↔°C).
category: physics
tags: [Thermodynamics, Enthalpy, Entropy, Gibbs Energy, Activation Energy, Arrhenius, Materials Science]
dependencies: ["numpy", "scipy", "sympy"]
---

# Thermodynamics

## Overview

Расчёт и верификация термодинамических величин для агентов opencode: enthalpy (энтальпия ΔH), entropy (энтропия ΔS), Gibbs free energy (энергия Гиббса ΔG), activation energy (энергия активации Ea), heat capacity (теплоёмкость Cp, модель Дебая), thermal conductivity (теплопроводность). Skill заточен под **материаловедение** (азотирование, цементация, отжиг, диффузия) и предназначен для двух ролей:

- **fact-checker** — проверка термодинамических клаймов в научных текстах (числовое соответствие, знаки, единицы).
- **researcher** — самостоятельные расчёты (Ea из двух точек Arrhenius, ΔG реакции, критерий спонтанности).

Skill **расширяет** `formulas.py` (добавляет термодинамические формулы-детекторы) и **направляет** на `numeric_comparator` для конвертации единиц и проверки размерностей.

## When to Use

Активировать, когда текст/задача содержит термодинамические утверждения:

- `Ea`, `Eа`, «энергия активации», «activation energy», «аррениус», `exp(-Ea/(RT))`, `Arrhenius`.
- `ΔG`, `ΔH`, `ΔS`, «энергия Гиббса», «энтальпия», «энтропия», «свободная энергия».
- `Cp`, «теплоёмкость», «теплоемкость», «Debye», «модель Дебая», `θ_D`.
- «теплопроводность», `thermal conductivity`, `k`, `λ`, `W/(m·K)`.
- Клаймы о спонтанности реакций, температурной зависимости, фазовых переходах.

Проверка клайма → сначала `detect_formula()` (расширенный) для идентификации формулы, затем числовое сравнение через `numeric_comparator`, затем unit conversion через `units.convert()`.

## Core Workflows

### 1. Arrhenius equation (Ea extraction) — Уравнение Аррениуса

**Формула:**
```
k = A · exp(-Ea / (R·T))
```
где `k` — константа скорости (rate constant), `A` — pre-exponential factor, `Ea` — энергия активации, `R = 8.314 J/(mol·K)` — газовая постоянная, `T` — абсолютная температура (K).

**Извлечение Ea из двух точек (наиболее частый клайм в материаловедении):**
```python
import numpy as np

R = 8.314  # J/(mol·K)

def arrhenius_ea(T1, k1, T2, k2):
    """Ea in J/mol from two (T, k) points."""
    return R * np.log(k2 / k1) / (1.0 / T1 - 1.0 / T2)

# Пример: азотирование 520°C → k=1e-4, 570°C → k=5e-4 (условно)
T1, k1 = 520 + 273.15, 1e-4
T2, k2 = 570 + 273.15, 5e-4
print(arrhenius_ea(T1, k1, T2, k2) / 1000, "kJ/mol")  # типично 70-80 kJ/mol
```

**Единицы:** `Ea` — J/mol (базово), на практике kJ/mol, kcal/mol, eV/atom. **T всегда в KELVIN** — °C перевести перед подстановкой.

**Верификация клайма:** если в тексте сказано «Ea = 75 кДж/моль для азотирования», а расчёт дал другой порядок → mismatch. Типичный диапазон см. Reference Values.

### 2. Gibbs free energy (ΔG = ΔH - TΔS)

**Формула:**
```
ΔG = ΔH - T·ΔS
```
**Критерий спонтанности:** ΔG < 0 → самопроизвольный; ΔG = 0 → равновесие; ΔG > 0 → несамопроизвольный.

```python
def gibbs(dH_kJ, dS_JperK, T_celsius):
    T = T_celsius + 273.15
    return dH_kJ * 1000 - T * dS_JperK  # ΔG в J/mol

# Пример: ΔH = -92 kJ/mol, ΔS = -198 J/(mol·K), T = 25°C
print(gibbs(-92, -198, 25) / 1000, "kJ/mol")  # -33 kJ/mol → spontaneous
```

**Единицы:** ΔH в kJ/mol (или J/mol), ΔS в J/(mol·K). `T·ΔS` даёт J/mol — **обязательно согласовать**: если ΔH в kJ, то либо T·ΔS перевести в kJ (÷1000), либо ΔH в J. Классическая ошибка — единицы ΔH и T·ΔS в разных масштабах.

**Reference ΔS ΔG для материаловедения** см. Reference Values.

### 3. Enthalpy/Entropy changes (ΔH, ΔS)

**Зависимость ΔH/ΔS от температуры (через heat capacity):**
```
ΔH(T) = ΔH° + ∫ Cp dT      (Kirchhoff's law)
ΔS(T) = ΔS° + ∫ (Cp/T) dT
```

```python
import numpy as np
from scipy.integrate import quad

def dH_kirchhoff(Cp_func, T1, T2, dH_ref):
    """dH_ref at T1; returns dH at T2 via Kirchhoff."""
    integ = quad(Cp_func, T1, T2)[0]
    return dH_ref + integ

# Cp(T) = a + b·T (J/mol·K), пример для стали
Cp = lambda T: 24.5 + 0.006*T
dH_900K = dH_kirchhoff(Cp, 298, 900, -20000)  # J/mol
```

**Знаки:** ΔH < 0 — экзотермическая (release heat), ΔH > 0 — эндотермическая (absorbs). ΔS > 0 — рост беспорядка.

### 4. Heat capacity (Cp, Debye model)

**Модель Дебая (низкотемпературная теплоёмкость твёрдых тел):**
```
Cv(T) = 9·N·kB·(T/θD)³ · ∫₀^(θD/T) x⁴·e^x / (e^x - 1)² dx
```
При низких T: `Cv ∝ T³` (Debye T³ law). При высоких T → Dulong-Petit `Cv = 3R` (≈ 24.9 J/(mol·K)).

```python
import numpy as np
from scipy.integrate import quad

kB = 1.380649e-23

def debye_cv(T, theta_D, N=1):
    """Cv in J/K per formula unit, N atoms per f.u."""
    x_max = theta_D / T
    f = lambda x: x**4 * np.exp(x) / (np.exp(x) - 1)**2
    I = quad(f, 0, x_max)[0]
    return 9 * N * kB * (T / theta_D)**3 * I
```

**Debye temperature θD:** для железа ~470 K, стали ~500-600 K, алюминия ~428 K. (Reference Values)

### 5. Thermal conductivity (теплопроводность)

**Формула (Wiedemann-Franz) для металлов:**
```
k = L · T · σ      (электронная)
L ≈ 2.44e-8 W·Ω/K²   (Lorentz number)
```

```python
L = 2.44e-8
def thermal_cond(T, sigma):   # sigma в S/m (сименс на метр)
    return L * T * sigma      # W/(m·K)
```

**Приемлемые значения (материаловедение):** сталь ~15-50 W/(m·K) (зависит от марки/обработки), медь ~400, алюминий ~200, керамика ~1-10. Для быстрой проверки клайма сравнить с этими референтными диапазонами.

### 6. Unit conversion (через numeric_comparator)

**Всегда используй `units.convert()` из инфраструктуры** (не пересчитывай руками).

```python
import sys
sys.path.insert(0, "/home/orangepi/projects/claimeai-service/scripts")
import units

# eV/atom ↔ kJ/mol: 1 eV/atom = 96.485 kJ/mol
E_kJ = units.convert(0.8, "ev_per_atom", "kj_per_mol")   # ~77.2
# K ↔ °C: аффинная, units учитывает offset
T_K = units.convert(25, "celsius", "kelvin")              # 298.15
T_C = units.convert(1273, "kelvin", "celsius")            # 999.85
# kJ/mol ↔ kcal/mol: 1 kJ = 0.239 kcal (нужно добавить kcal в registry)
```

**Доступные единицы энергии (units.py):** `kj_per_mol`, `ev_per_atom` — взаимоконвертируемы (96.485). **Добавь `kcal_per_mol`** в units.py при необходимости (1 kcal = 4.184 kJ).

**Dimension check (проверка размерности):** если клавия утверждает соотношение, а размерности не совпадают → `not_comparable`:
```python
from units import dimension
assert dimension("kj_per_mol") == dimension("ev_per_atom")  # одинаковый (энергия на моль)
```

**Всегда** приводите T к Кельвину перед подстановкой в exp/ln (Arrhenius, ΔG).

## Common Pitfalls

1. **Unit mismatch (eV vs kJ/mol)** — самая частая ошибка. Ea из текста может быть в eV/atom (напр. 0.8 эВ) — это НЕ то же, что kJ/mol. Конвертируй через `units.convert` (×96.485). Никогда не сравнивай 80 кДж/моль с 0.8 эВ напрямую.
2. **Температура в Celsius вместо Kelvin** — экспонента Arrhenius требует абсолютную T. `exp(-Ea/(R·T))` с T=570 вместо 843K даст абсурд. Всегда +273.15.
3. **Знак ΔG и ΔH** — знаковые соглашения: ΔH < 0 экзотермический (обычно спонтанный при высокой T), но ΔS<0 может перевернуть. Проверяй `ΔG = ΔH - TΔS`, не только знак ΔH.
4. **Разномасштабные единицы в ΔG = ΔH - TΔS** — ΔH в kJ/mol, ΔS в J/(mol·K): T·ΔS в J, а ΔH в kJ → нельзя вычитать. Приведи к одному масштабу.
5. **R (газовая постоянная) с неправильными единицами** — R = 8.314 J/(mol·K) ≠ 0.008314 kJ/(mol·K). В расчёте с kJ переводи либо Ea, либо R.
6. **Ea «похоже» на ΔH** — энергия активации ≠ энтальпия реакции. Arrhenius Ea для диффузии ~100-200 кДж/моль, а ΔH реакции может быть мал/отрицателен. Не путай.
7. **Debye-модель в пределых** — при T > θ_D Cv ~3R (Dulong-Petit, больше не растёт). Клайм Cv при высоких T может казаться линейным — проверь.

## Integration with our tools

- **`formulas.py`** (`/home/orangepi/projects/claimeai-service/scripts/formulas.py`): `detect_formula(text)` уже находит `arrhenius` (паттерны: «аррениус», «arrhenius», `exp(-ea/(rt))`). **Этот skill расширяет**: добавить thermo-паттерны в `FORMULA_MARKERS`:
  ```python
  # РАСШИРЕНИЕ formulas.py (предлагаемое):
  # "gibbs": {"patterns": ["gibbs", "энергия гиббса", "Δg =", "dg ="], "constants": {}},
  # "enthalpy": {"patterns": ["энтальп", "enthalp", "Δh", "dh"], "constants": {}},
  # "entropy": {"patterns": ["энтроп", "entrop", "Δs", "ds"], "constants": {}},
  # "heat_capacity": {"patterns": ["теплоёмк", "теплоемк", "heat capacity", "cp", "debye", "θd"], "constants": {}},
  ```
- **`numeric_comparator.py`**: вызывай `compare_claims`/numeric-слой для числового сопоставления claim vs source; после — `units.dimension()` для проверки размерностей; знай что `detect_formula()` вызывается внутри, и `formula_conflict` → mismatch.
- **`units.py`**: `units.convert()`, `units.dimension()`, `units.normalize_unit()`. Доступны энергия (kj_per_mol, ev_per_atom), темп (celsius, kelvin), диффузия (cm2_per_s, m2_per_s). Для термодинамики добавь `kcal/mol`, `W_per_mK` при необходимости.
- **`dimensional-analysis` skill** (`~/.config/opencode/skills/dimensional-analysis/`): Buckingham Pi + нон-дименсионализация — используй для проверки, что производная термо-величина размерностно корректна, и для сокращения параметрного пространства в многофакторных задачах (например, что в диффузии входит D·t / L²).

## Reference Values

### Энергия активации Ea (activation energy, материаловедение)

| Процесс | Ea, кДж/моль | Ea, эВ | Примечание |
|---|---|---|---|
| Азотирование (nitriding) | 70–80 | ~0.73–0.83 | насыщение азотом |
| Цементация (carburizing) | 100–140 | ~1.0–1.45 | науглероживание |
| Отжиг/диффузия азота в стали | 100–200 | ~1.0–2.1 | диффузия в Fe |
| Диффузия углерода в феррит | ~80–95 | ~0.83–0.98 | |
| Диффузия углерода в аустените | ~135–150 | ~1.4–1.55 | |
| Диффузия железа в Fe | ~240–280 | ~2.5–2.9 | самодиффузия |

### Энтальпия реакции ΔH (reference)

| Реакция | ΔH° (кДж/моль) | Тип |
|---|---|---|
| H₂ + ½O₂ → H₂O (г) | −241.8 | экзотерм |
| 2C + O₂ → 2CO | −221 | экзотерм |
| Fe₃C (карбид) разложение | ~ −17 (ΔG° при 700°C) | слабоэкзотерм |
| Азотирование (N₂ → 2N в стали) | (эндот, ~высок) | эндо |

### Температура Дебая θ_D и теплоёмкость

| Материал | θ_D (K) | Примечание |
|---|---|---|
| Al | ~428 | |
| Fe | ~470 | |
| Сталь | ~500–600 | |
| Cu | ~343 | |
| Cv при T >> θ_D | 3R ≈ 24.9 J/(mol·K) | Dulong–Petit limit |

### Теплопроводность k (W/(m·K))

| Материал | k (W/(m·K)) |
|---|---|
| Медь Cu | ~385–400 |
| Алюминий Al | ~205–235 |
| Сталь (мягкая) | ~45–50 |
| Сталь (нержав.) | ~15–20 |
| Кова (cast iron) | ~50–80 |
| Азотная сталь (нитридный слой) | ниже базовой стали |

### Диффузия (диффusion coefficient unit см²/с)

| Система | D₀ (см²/с) | Q (кДж/моль) |
|---|---|---|
| C в α-Fe | ~0.02 | ~80–95 |
| C в γ-Fe | ~0.2 | ~135–150 |
| N в Fe (ε) | ~0.003 | ~100–150 |

> **Типичная проверка:** при валидации клавия «Ea азотирования 75 кДж/моль» — сопоставить с диапазоном 40–80 кДж/моль. Выход за диапазон → флаг для перепроверки (unit mismatch eV↔kJ, или sign).

## Usage Example (fact-check)

```python
import sys
sys.path.insert(0, '/home/orangepi/projects/claimeai-service/scripts')
from formulas import detect_formula, check_constant
from units import convert, dimension

claim = "Энергия активации азотирования составила 0.8 эВ (77 кДж/моль), процесс подчиняется уравнению Арреннус."
f = detect_formula(claim)                    # -> 'arrhenius'
eV = 0.8
kj = convert(eV, "ev_per_atom", "kj_per_mol")  # ~77.2 кДж/моль
assert abs(kj - 77) < 2.5                     # согласовано
assert dimension("ev_per_atom") == dimension("kj_per_mol")  # оба — energy
```
→ Единицы согласованы, значение в норме, клайм численно **consistent**.

## Integration with our tools summary

| Tool | Использование |
|---|---|
| `formulas.py` | `detect_formula()` — распознать thermo-формулу в тексте |
| `numeric_comparator.py` | численное сопоставление claim↔source; `formula` → mismatch если константа конфликт |
| `units.py` | `convert()`, `dimension()`, `normalize_unit()` для unit-safe расчётов |
| `dimensional-analysis` | Buckingham Pi, неразмерсиализация для сложных термо-моделей |
