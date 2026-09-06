---
name: stoichiometry
description: Balance chemical equations and compute stoichiometric ratios, limiting reagent, theoretical/percent yield. Use when verifying reaction claims, computing molar ratios, or checking mass balance.
category: chemistry
license: Apache-2.0 license
metadata:
    skill-author: doc_guard factory
version: 1.0.0
tags: [Stoichiometry, Balancing, Molar Ratios, Limiting Reagent, Yield, Mass Balance]
dependencies: ["sympy>=1.12", "rdkit-pypi>=2024.3.1"]
---

# Stoichiometry Skill

## Overview

Balance chemical equations and perform stoichiometric calculations: molar ratios, limiting reagent, theoretical yield, percent yield, and mass-balance verification. This skill is the **general stoichiometry** gap-filler (openscience ships only `cobrapy` for metabolic FBA, not general reaction stoichiometry). It is used by the **researcher** and **fact-checker** agents to verify reaction claims and compute molar quantities.

**Key capabilities**:
- Algebraic equation balancing via linear-system solve (sympy)
- Mole-to-mole conversions from balanced equations
- Limiting-reagent determination from available moles
- Theoretical yield from the limiting reagent
- Percent yield from actual/theoretical
- Conservation-of-mass verification

## Installation and Setup

```bash
uv pip install sympy
uv pip install rdkit-pypi   # optional: molecular weights via RDKit
```

**Import convention**:
```python
import sympy as sp
```

## Reference: Atomic Masses (g/mol)

| Element | Mass | Element | Mass |
|---------|------|---------|------|
| H  | 1.008  | Fe | 55.845 |
| C  | 12.011 | N  | 14.007 |
| O  | 15.999 | S  | 32.06  |
| Na | 22.990 | Cl | 35.45  |
| Mg | 24.305 | K  | 39.098 |
| Al | 26.982 | Ca | 40.078 |
| Si | 28.085 | Cu | 63.546 |
| P  | 30.974 | Zn | 65.38  |

For any other element, use `rdkit.Chem.rdMolDescriptors.CalcMolWt` on the SMILES, or a periodic-table source. **Never hardcode a mass you are unsure of** — verify against a reference.

## Workflows

### 1. Equation Balancing (algebraic / linear system)

For `aA + bB → cC + dD`, set up one linear equation per element and solve for integer coefficients.

```python
import sympy as sp

def balance(elements, species):
    """
    elements: list of element symbols, e.g. ['Fe','O']
    species:  list of dicts {element: count} for each species in order
              [reactant1, reactant2, product1, product2]
    Returns integer coefficients [a, b, c, d] or None if unsolvable.
    """
    n = len(species)
    coeffs = sp.symbols('c0:%d' % n)
    eqs = []
    for el in elements:
        lhs = sum(coeffs[i] * species[i].get(el, 0) for i in range(n))
        eqs.append(sp.Eq(lhs, 0))
    # fix c0 = 1 to avoid trivial zero solution
    eqs.append(sp.Eq(coeffs[0], 1))
    sol = sp.solve(eqs, coeffs, dict=True)
    if not sol:
        return None
    s = sol[0]
    vals = [sp.Rational(s.get(c, 0)) for c in coeffs]
    # scale to smallest integers
    lcm = 1
    for v in vals:
        lcm = sp.ilcm(lcm, sp.denom(v))
    ints = [int(v * lcm) for v in vals]
    g = sp.gcd(*[abs(x) for x in ints])
    return [x // g for x in ints]

# Fe + O2 -> Fe2O3
species = [
    {'Fe': 1},            # Fe
    {'O': 2},             # O2
    {'Fe': 2, 'O': 3},    # Fe2O3
]
print(balance(['Fe', 'O'], species))  # [4, 3, 2]  -> 4Fe + 3O2 -> 2Fe2O3
```

**Worked examples**:
- Combustion: `CH4 + O2 → CO2 + H2O` → `1, 2, 1, 2`
- Oxidation: `Fe + O2 → Fe2O3` → `4, 3, 2`
- Nitriding: `Fe + N2 → Fe4N` → `8, 1, 2`

### 2. Molar Ratios

From the balanced equation, the coefficients ARE the mole ratios. Convert between any two species:

```python
def mole_ratio(coeff_from, coeff_to):
    """Moles of target per mole of source (from balanced coefficients)."""
    return coeff_to / coeff_from

# 4Fe + 3O2 -> 2Fe2O3 : moles of O2 per mole of Fe
print(mole_ratio(4, 3))  # 0.75 mol O2 per mol Fe
```

Mole-to-mole conversion: `moles_target = moles_source * (coeff_target / coeff_source)`.

### 3. Limiting Reagent

Compare available moles against the required ratio. The species that runs out first is limiting.

```python
def limiting_reagent(available_moles, coeffs):
    """
    available_moles: dict {species: moles_available}
    coeffs:          dict {species: balanced_coefficient}
    Returns the limiting species name.
    """
    ratios = {s: available_moles[s] / coeffs[s] for s in coeffs}
    return min(ratios, key=ratios.get)

# 4Fe + 3O2 -> 2Fe2O3 ; have 2 mol Fe, 1.5 mol O2
print(limiting_reagent({'Fe': 2, 'O2': 1.5}, {'Fe': 4, 'O2': 3}))
# Fe: 2/4=0.5, O2: 1.5/3=0.5 -> tie (both limiting, exact stoichiometry)
```

### 4. Theoretical Yield

Maximum product from the limiting reagent:

```python
def theoretical_yield(limiting_moles, coeff_limiting, coeff_product, molar_mass_product):
    """Product mass (g) from limiting reagent moles."""
    product_moles = limiting_moles * (coeff_product / coeff_limiting)
    return product_moles * molar_mass_product
```

### 5. Percent Yield

```python
def percent_yield(actual_mass, theoretical_mass):
    return (actual_mass / theoretical_mass) * 100.0
```

### 6. Mass Balance (conservation of mass)

Total mass of reactants must equal total mass of products (within rounding):

```python
def mass_balance(coeffs, molar_masses):
    """
    coeffs:       dict {species: coefficient}
    molar_masses: dict {species: g/mol}
    Returns (reactant_mass, product_mass, diff_g).
    """
    # split species into reactants/products by sign convention in caller
    total = sum(coeffs[s] * molar_masses[s] for s in coeffs)
    return total
```

For a full check, sum reactant masses and product masses separately and assert `abs(diff) < 0.01 * total`.

## Common Pitfalls

1. **Unbalanced equations** — always balance before computing ratios. An unbalanced equation gives wrong molar ratios and wrong limiting reagent.
2. **Wrong limiting reagent** — compare `moles/coefficient`, not raw moles. A species with more moles can still be limiting if its coefficient is large.
3. **Unit confusion (g vs mol)** — convert mass to moles via `n = m / M` before any ratio math. Never divide grams by grams-per-mole and treat the result as moles without checking units.
4. **Rounding too early** — keep rational coefficients (sympy `Rational`) until the final integer scaling; premature float rounding can flip a near-tie limiting reagent.
5. **Tie in limiting reagent** — when two species give the same `moles/coefficient`, both are limiting (exact stoichiometry); report it, don't guess.
6. **Percent yield > 100%** — physically impossible for a pure product; indicates measurement error, impure product, or a wrong theoretical yield.

## Integration

- **numeric_comparator** (`scripts/numeric_comparator.py`): use its unit registry for `mol`, `g`, `g/mol` when comparing claimed vs computed quantities. Feed computed values through `compare_single` / `compare_ranges` for fact-checking.
- **rdkit** (`rdkit.Chem.rdMolDescriptors.CalcMolWt`): compute molecular weights from SMILES instead of hardcoding, especially for complex molecules.
- **formulas.py** (`scripts/formulas.py`): for materials-science reactions (Scherrer, Williamson-Hall, Arrhenius) that build on stoichiometric quantities, reuse the same unit conventions.

## Verification Checklist

- [ ] Equation is balanced (atom count equal on both sides).
- [ ] Molar masses verified against a reference (not guessed).
- [ ] Mass converted to moles before ratio math.
- [ ] Limiting reagent identified by `moles/coefficient`, not raw moles.
- [ ] Theoretical yield derived from the limiting reagent only.
- [ ] Percent yield computed as actual/theoretical × 100.
- [ ] Mass balance holds within rounding tolerance.
