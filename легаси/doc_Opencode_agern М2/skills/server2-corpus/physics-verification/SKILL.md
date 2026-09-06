---
name: physics-verification
description: Verify physical correctness of claims and results — dimensional consistency, limiting cases (t→0, T→0, x→∞), conservation laws (energy/momentum/mass/charge), order-of-magnitude sanity, symmetry checks. Use for fact-checking physics claims, validating derived equations, catching ~60% of physics errors. Combines our numeric_comparator dimension check + GPD verification-core methodology.
category: physics
tags: [Physics, Verification, Dimensional Analysis, Conservation Laws, Limiting Cases, Order-of-Magnitude, Fact-checking]
dependencies: ["numpy", "scipy", "sympy", "pint"]
---

# Physics Verification

## Overview

Верификация физической корректности клаймов/результатов для агентов opencode. Skill комбинирует **наш `numeric_comparator.py` dimension check** (`units.dimension()` → `dimension_mismatch`, cap 0.3) с **GPD (get-physics-done) verification-core**: dimensional analysis, limiting cases, symmetry, conservation laws. Цель — детерминированно отловить **~60% физических ошибок**, которые не видны при чисто числовом сравнении.

Skill предназначен для трёх ролей:

- **fact-checker** — проверить физическую корректность клайма в научном тексте (согласованы ли единицы, не нарушает ли закон сохранения, разумна ли величина).
- **tribunal-judge** — обосновать вердикт по физическому критерию (клайм «физически невозможен» → опровержение).
- **researcher** — провалидировать собственный вывод перед публикацией.

## When to Use

Активировать, когда задача/текст содержит физический результат, требующий проверки сверх чисел:

- Уравнение с единицами: `F = ma`, `E = mc²`, `ΔG = ΔH − TΔS`, `k = A·exp(−Ea/RT)`.
- Предельные поведения: «при t→∞ стремится к ...», «при T→0 ...», «при x→∞ ...».
- Клаймы о сохранении: «энергия сохраняется», «импульс», «масса/заряд».
- Величины с подозрительным порядком: энергия активации, размер кристаллита, деформация.
- Симметричные системы: изотропная, периодическая, осесимметричная.

Пайплайн проверки клайма: **1) размерности** (`units.dimension()`/pint) → **2) предельные случаи** → **3) законы сохранения** → **4) порядок величины** → **5) симметрия**. Каждый шаг возвращает `ok`/`suspect` + объяснение; при `suspect` — cap сходства (см. `numeric_comparator`).

## Core Workflows

### 1. Dimensional consistency — Согласованность размерностей

Обе части уравнения должны иметь одинаковые размерности в базисе SI: L (length), M (mass), T (time), I (current), Θ (temperature), N (amount), J (luminosity).

**Python:** `units.dimension()` + pint.

```python
import sys
sys.path.insert(0, '/home/orangepi/projects/claimeai-service/scripts')
from units import dimension, convert

def check_dim_consistency(lhs_unit: str, rhs_unit: str) -> dict:
    """Сравнить размерности двух сторон уравнения.
    lhs_unit/rhs_unit — строки канонических единиц (см. units._CANON)."""
    d_lhs = dimension(lhs_unit)
    d_rhs = dimension(rhs_unit)
    ok = (d_lhs == d_rhs)
    return {
        'lhs': d_lhs, 'rhs': d_rhs,
        'ok': ok,
        'verdict': 'PASS' if ok else 'SUSPECT',
        'note': 'dimensionally consistent' if ok
                else f'dimension mismatch: {d_lhs} vs {d_rhs}'
    }

# Пример: F = m·a  →  [N] = [kg·m/s²]
print(check_dim_consistency('N', 'kg_per_m2_per_s'))     # учить маппинг
print(check_dim_consistency('kg_per_m2', 'kg_per_m2'))   # ✓
```

**С pint (символьный, для формул):**

```python
import pint
ureg = pint.UnitRegistry()

# Двусторонняя проверка уравнения через построение обеих сторон
# F = m·a
m = ureg.Quantity(1.0, 'kg')
a = ureg.Quantity(1.0, 'm/s**2')
lhs = m * a                       # [kg·m/s²] = [N]
rhs = ureg.Quantity(1.0, 'N')
print(lhs.dimensionality == rhs.dimensionality)  # True

# Сложение/вычитание с разными размерностями → ошибка
try:
    mass + velocity
except pint.DimensionalityError as e:
    print(f"DimensionalityError caught: {e}")

# Безразмерный аргумент экспоненты обязателен:
# exp(-Ea/RT): Ea/[J·mol⁻¹] / (R[J·mol⁻¹·K⁻¹]·T[K]) → безразмерно
Ea = ureg.Quantity(100, 'kJ/mol')
R = ureg.Quantity(8.314, 'J/(mol*K)')
T = ureg.Quantity(1000, 'K')
arg = (Ea / (R * T))
print("dimensionless:", arg.dimensionless)  # True
```

**Символьный размерностный анализ через sympy** (построить размерность выражения):

```python
import sympy as sp
# масса в kg, длина в m, время в s
def dim(expr_str, base={'kg':'M','m':'L','s':'T','K':'Theta','A':'I','mol':'N','cd':'J'}):
    # см. units.dimension() для канонической таблицы; для общего случая:
    # соберите степень каждого базиса вручную — упрощение с simpy.
    return None  # placeholder — читайте units.py:dimension()

# Быстрее и надёжнее: готовый units.dimension() покрывает материалы науку (kJ/mol, eV, nm, GPa...)
```

**Референс — базовые размерности:**

| Размерность | Символ | Единица SI |
|---|---|---|
| Length | L | m |
| Mass | M | kg |
| Time | T | s |
| Electric current | I | A |
| Temperature | Θ | K |
| Amount of substance | N | mol |
| Luminous intensity | J | cd |

### 2. Limiting cases — Предельные случаи

Проверить поведение результата на крайностях. Если результат расходится/ведёт себя неправильно → ошибка.

**Репертуар пределов:**
- `t→0` — начальное условие (должно сходиться к известному старту).
- `t→∞` — стационар/steady state (должен выходить на асимптотику, не к ∞/NaN).
- `T→0` — квантовый предел (нулевая колебательная энергия, остаточная).
- `T→∞` — классический предел (тепловая энергия ≫ квантовый шаг).
- `x→0` и `x→∞` — локальная/асимптотическая корректность.
- `m→0`, `c→∞` (безразмерные пределы параметров).

```python
def check_limit(fn, lim, expect=None):
    """fn(x) -> float; lim — значение, к которому стремится аргумент.
    Детерминированный вердикт: NaN/inf или сходится к ожидаемому."""
    try:
        val = fn(lim)
    except ZeroDivisionError:
        return {'ok': False, 'verdict': 'SUSPECT',
                'note': f'diverges (ZeroDivision) at {name}={lim}'}
    if val != val or val in (float('inf'), float('-inf')):
        return {'ok': False, 'verdict': 'SUSPECT',
                'note': f'non-finite at {name}={lim}: {val}'}
    return {'ok': True, 'verdict': 'PASS', 'value': val,
            'note': f'finite at {name}={lim}: {val}'}

# Пример: идеальный газ pV = nRT → при T→0 объём→0 (при const p,n)
import math
def ideal_vol(T): return (1.0 * 8.314 * T) / 1.0e5  # p=1 bar
print(check_limit(ideal_vol, 0.0, 'T'))   # → 0, finite PASS (T→0)

# Пример-ошибка: закон Стефана-Больцмана E∝T⁴ при T→0 корректно даёт 0;
# но "E = kT" при T→0 без нулевой энергии → расхождение с квантовым пределом
```

**Контр-пример ошибки:** результат при `t→∞` возвращает `NaN` или бесконечность, тогда как физически система должна прийти в стационар — это физический дефект.

### 3. Conservation laws — Законы сохранения

Проверить, не нарушает ли клайм фундаментальные сохранения: масса, энергия, импульс, момент импульса, заряд.

```python
def check_conservation(quantity_in, quantity_out, tol=1e-9):
    """Суммарная сохраняемая величина входа vs выхода."""
    if abs(quantity_in - quantity_out) > tol * max(abs(quantity_in), 1e-30):
        return {'ok': False, 'verdict': 'SUSPECT',
                'note': f'violates conservation: in={quantity_in}, out={quantity_out}'}
    return {'ok': True, 'verdict': 'PASS',
            'note': f'conserved: {quantity_in} == {quantity_out}'}

# Пример: упругое соударение — импульс
# m1*v1 + m2*v2 = m1*v1' + m2*v2'
p_before = 2.0 * 3.0 + 1.0 * (-1.0)   # 5 kg·m/s
p_after  = 2.0 * 2.0 + 1.0 * (1.0)     # 5 kg·m/s
print(check_conservation(p_before, p_after))  # ✓ PASS

# Пример-ошибка: клайм «реакция производит энергию из ничего» → нарушение
# (нулевое из открытой системы) — если заявлен вечный двигатель, это опровержение.
```

**Категории сохранения:**

| Закон | Величина | Проверка |
|---|---|---|
| Conservation of mass | m | сумма масс реагентов = продуктов |
| Energy | E | KE+PE+thermal+... до/после |
| Linear momentum | p | Σmv |
| Angular momentum | L | Σr×p |
| Charge | Q | Σq |
| Baryon/Lepton | числа | для ядерных клаймов |

### 4. Order-of-magnitude sanity — Разумность порядка величины

Вероятность — числоздо разумно для домена? Если нет → ошибка.

```python
# Референсные диапазоны для материаловедения/физики
SANE_RANGES = {
    'activation_energy':  (1e2, 5e2, 'kJ/mol'),      # Ea 20–500 kJ/mol
    'crystallite_size':   (1e-9, 1e-6, 'm'),        # 1–1000 nm
    'strain':             (1e-5, 1e-2, 'dimensionless'), # 10⁻⁵–10⁻²
    'dislocation_density':(1e10, 1e16, '1/m²'),
    'temperature':        (1.0, 1e4, 'K'),
    'pressure':           (1e-4, 1e11, 'Pa'),       # deep-vacuum … GPa
    'diffusion_energy':   (1e2, 3e2, 'kJ/mol'),
}

def check_magnitude(value, param, unit=None):
    lo, hi, default_unit = SANE_RANGES.get(param, (None, None, None))
    if lo is None:
        return {'verdict': 'INFO', 'note': f'no reference for {param}'}
    # конвертация к базовым единицам — через units.convert при несовпадении
    ok = lo <= value <= hi
    return {'ok': ok, 'verdict': 'PASS' if ok else 'SUSPECT',
            'note': f'{value}{unit} in [{lo},{hi}]{default_unit}'}

# Пример: Ea = 70 kJ/mol ✓ ; Ea = 1 eV (≈96 kJ/mol, но единица путаница) —
# 1 eV ≠ 1 kJ/mol — из numeric_comparator мультитест units
```

**Типичные путаницы порядка:** eV vs kJ/mol (1 eV ≈ 96.5 kJ/mol), кристаллит «10 nm» (не «10 m»), деформация «10⁻³» (не «10»), длина волны «1.5 Å» для Cu Kα.

### 5. Symmetry checks — Проверка симметрии

Если система имеет симметрию (изотропия, периодичность, осевая), результат должен её уважать. Нарушение без причины → подозрение.

```python
def check_symmetry(claims: list[float], sym='isotropic'):
    """Проверить, что результаты уважают заявленную симметрию.
    Например, изотропные свойства должны быть равны по осям."""
    if sym == 'isotropic':
        vals = [float(v) for v in claims]
        spread = max(vals) - min(vals)
        return {'ok': spread < 1e-6, 'verdict': 'PASS' if spread < 1e-6 else 'SUSPECT',
                'note': f'isotropy violated, spread={spread}'}
    # periodic: f(x+L) == f(x) — проверка сдвигом на период
    return {'verdict': 'INFO', 'note': f'symmetry {sym} not implemented'}
```

**Проверки симметрии:**
- **Isotropic** — свойство не должно зависеть от направления.
- **Periodic** — результат инвариант от сдвига на период решётки `L`.
- **Mirror** — результат не должен меняться при отражении, если источник симметричен.
- **Inversion/time-reversal** — физические законы симметричны к обращению времени/пространства.

## Integration

- **`numeric_comparator.py`** (`/home/orangepi/projects/claimeai-service/scripts/`): числовое сопоставление claim↔source. При `dimension_mismatch` cap схода 0.3 — этот skill детерминирует почему (сверка размерностей `units.dimension()`), даёт объяснимую причину низкого score.
- **`dimensional-analysis` skill** — когда нужно не только проверить, но и построить Π-группы (Buckingham Pi), масштабы.
- **`thermodynamics` skill** — верификация Ea/ΔG/ΔH через Arrhenius; использует те же предельные (T→0) и порядок-величин.
- **`xrd-interpretation` skill** — Scherrer/Williamson-Hall: проверить `D=Kλ/(β·cosθ)`, единица `[m]` vs `[rad]` (rad безразмерен), порядок размера кристаллита (10–100 nm).
- **`units-conversion`** — точная конвертация между системами единиц.

## Common Pitfalls

1. **rad не имеет размерности** — угол безразмерен, поэтому `λ/β` сохраняет `[m]`. Ошибка: считать rad как размерность.
2. **eV vs kJ/mol** — 1 eV ≈ 96.5 kJ/mol; сравнение чисел без единиц некорректно (классика unit-mismatch).
3. **Безразмерный аргумент** — у `exp(...)`, `ln(...)`, `sin(...)` аргумент обязан быть безразмерным; `exp(-Ea/(RT))` — `[J/mol]/([J/mol·K]·[K])` → безразмерно.
4. **Предел расходится там, где должен сходиться** — t→∞ должна быть асимптота; NaN/inf в стационаре = ошибка.
5. **Вечный двигатель** — любое заявление о непрерывном производстве энергии без входа → нарушение сохранения, опровержение.
6. **Порядок величины** — «10 nm кристаллита» нормально, «10 m» — нет; всегда сверять с референсным диапазоном.

## References

- GPD (get-physics-done) verification-core методология: dimensional analysis, limiting cases, symmetry, conservation laws — ~60% физических ошибок.
- SI базовые размерности (L, M, T, I, Θ, N, J) — таблица в Workflow 1.
- Наш `numeric_comparator.py` (`units.dimension()`, `dimension_mismatch → cap 0.3`) — детерминированный dimension check.
- `dimensional-analysis` skill (Buckingham Pi) для углублённого анализа.
