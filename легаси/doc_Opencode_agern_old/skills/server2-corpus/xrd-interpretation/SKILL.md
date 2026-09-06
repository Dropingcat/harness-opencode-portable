---
name: xrd-interpretation
description: Interpret powder X-ray diffraction (XRD) patterns — peak indexing (Miller indices hkl), d-spacing (Bragg's law), crystallite size (Scherrer), microstrain + crystallite size (Williamson-Hall), dislocation density, and phase identification against ICDD/JCPDS cards. Use for any calculation or claim about crystal structure, crystallite size, microstrain, or dislocation density derived from diffraction data in materials science.
category: physics
version: 1.0.0
author: ours (D3)
license: MIT
tags: [XRD, diffraction, Scherrer, Williamson-Hall, Bragg, Miller indices, crystallite size, microstrain, dislocation density, pymatgen]
dependencies: ["numpy>=1.24.0", "scipy>=1.11.0", "pymatgen>=2023.x"]
---

# XRD Interpretation

## Overview

Interpret powder X-ray diffraction (XRD) patterns and verify claims about crystal structure, crystallite size, microstrain, and dislocation density. The skill covers the six canonical analyses:

1. **Bragg's law** — d-spacing from peak positions: `nλ = 2d·sinθ`
2. **Scherrer equation** — crystallite size from peak broadening: `D = Kλ/(β·cosθ)`
3. **Williamson-Hall** — separates size and microstrain broadening: `β·cosθ = Kλ/D + 4ε·sinθ`
4. **Dislocation density** — `ρ = 1/D²` (or `3/D²`)
5. **Phase identification** — match observed peaks to ICDD/JCPDS cards / simulated pymatgen patterns
6. **Peak indexing** — assign Miller indices (hkl) to reflections

Primarily for the **researcher** (calculation) and **fact-checker** (verification of claims about crystallite size, strain, d-spacing) agents.

## When to Use

- A claim or task involves crystallite size, crystallite/grain dimension (e.g. "crystallite size of 24 nm")
- Microstrain or lattice strain values reported (ε ~ 10⁻³–10⁻⁴)
- Dislocation density (ρ) values quoted in units of m⁻² or cm⁻²
- Peak indexing / Miller indices assignment (hkl)
- Phase identification from powder patterns (matching to ICDD/JCPDS)
- Any Bragg-angle → d-spacing conversion or vice versa

## Core Workflows

### 1. Bragg's law (d-spacing: nλ = 2d·sinθ)

Compute interplanar spacing d from the diffraction angle. **θ is in radians** inside the trig function; input angles are usually 2θ in degrees.

```python
import numpy as np

def d_spacing(two_theta_deg, wavelength_A=1.5406, n=1):
    """d-spacing from 2θ. wavelength in Å, 2θ in degrees."""
    theta = np.radians(two_theta_deg / 2.0)  # θ = 2θ/2 → radians
    return n * wavelength_A / (2.0 * np.sin(theta))

# Cu Kα (most common)
print(f"d(111)@2θ=38.1°: {d_spacing(38.1):.4f} Å")   # ~2.36 Å (Au 111)
print(f"d(110)@2θ=44.7°: {d_spacing(44.7):.4f} Å")   # ~2.03 Å (Fe 110)

# Co Kα and Mo Kα give different 2θ for the SAME d → do not mix λ sources.
print(f"d(111) Au with Mo Kα: {d_spacing(38.1, lambda=0.71073):.4f} Å")
```

**Units:** `d` in angstroms (Å), λ in Å. Angle unit registry (`numeric_comparator`): `°`, `deg`, `rad`.

### 2. Scherrer equation (crystallite size: D = Kλ/(β·cosθ))

Average crystallite (coherent domain) size from FWHM of a peak.

```python
def scherrer(fwhm_deg, two_theta_deg, lambda=1.5406, K=0.9):
    """D in nm. Inputs: FWHM and 2θ in degrees; λ in angstroms."""
    beta = np.radians(fwhm_deg)                      # FWHM in radians (required!)
    theta = np.radians(two_theta_deg / 2.0)          # Bragg angle in radians
    D_nm = K * lambda / (beta * np.cos(theta)) / 10.0  # Å → nm
    return D_nm

# Example: FWHM=0.5° at 2θ=40° → ~16.6 nm
print(f"D = {scherrer(0.5, 40.0):.1f} nm")
```

**K factor** (shape factor):
- **K = 0.9** — spherical crystallites (most common default)
- **K = 1.0** — cubic particles
- `K` is dimensionless; claim-checking: `formulas.py` flags `0.9` as `formula_consistent`, `1.0`/`K=1` as `formula_conflict` (it treats 0.9 as canonical). Report which K the source used.

**Crystallite size caveats:**
- Applicable only for **D ≲ 100 nm** (instrumental broadening dominates beyond).
- Typical crystallite sizes: **10–100 nm** for most metals/ceramics.
- FWHM must be **instrumental-broadening-corrected** (see Williamson-Hall or use NIST/Si standard) — raw FWHM overestimates 1/D.

### 3. Williamson-Hall (microstrain + crystallite size: β·cosθ = Kλ/D + 4ε·sinθ)

Separates size (constant in `β·cosθ`) from strain (grows with `sinθ`). Plot `β·cosθ` vs `4·sinθ`: **slope = ε**, **intercept = Kλ/D**.

```python
import numpy as np

def williamson_hall(two_theta_deg, fwhm_deg, K=0.9, lambda=1.5406):
    """Inputs: arrays of 2θ and FWHM in degrees.
    Returns (D_nm, eps)."""
    theta = np.radians(two_theta_deg / 2.0)
    beta  = np.radians(fwhm_deg)
    y = beta * np.cos(theta)          # y = βcosθ
    x = 4.0 * np.sin(theta)           # x = 4sinθ
    slope, intercept = np.polyfit(x, y, 1)
    eps = slope                        # microstrain
    D_nm = K * lambda / intercept / 10.0  # D in nm
    return D_nm, eps

# example data: peaks 111,200,220,311 of a nanocrystalline metal
two_theta = np.array([43.3, 50.4, 74.1, 89.9])
fwhm      = np.array([0.45, 0.52, 0.68, 0.80])
D, eps = williamson_hall(two_theta, fwhm)
print(f"D = {D:.1f} nm, ε = {eps:.4f} ({eps:.2e})")
```

**ε typical range:** **10⁻⁴–10⁻³** (dimensionless). If a claim quotes ε outside ~10⁻⁵–10⁻², it's suspect.

**Limitations / alternatives:**
- W-H is a 1st-order (isotropic) model; strain is anisotropic → multiple peaks scatter.
- Use **modified WH** (adds higher-order ε terms) or **Warren-Averbach** for rigorous size/strain separation.
- Requires ≥3–4 peaks across a wide 2θ range for a meaningful fit.

### 4. Dislocation density (ρ = 1/D² или ρ = 3/D²)

Estimated from crystallite size (approximation; common in metals literature).

```python
def dislocation_density(D_nm, factor=1.0):
    """ρ ≈ factor / D². D in nm → returns ρ in m⁻²."""
    D_m = D_nm * 1e-9
    return factor / D_m**2

# D=20 nm → ρ ≈ 2.5e15 m⁻²  (typical range 1e14–1e16 m⁻² for deformed metals)
print(f"ρ = {dislocation_density(20.0):.2e} m⁻²")
```

**Units:** ρ is **m⁻²** (SI) or **cm⁻²** (CGS). `numeric_comparator` registry includes `см²/с`, `м²/с` — convert consistently. `formula.py` detects dislocation marker patterns `"дислокац"`, `"ρ ="`, `"rho"`, `"плотность дислокаций"`.

**Typical ranges:** annealed metals `1e12–1e14 m⁻²`, cold-worked `1e14–1e16 m⁻²`. Order-of-magnitude cross-check is essential.

### 5. Phase identification (match peaks to ICDD/JCPDS cards)

Match observed peak positions against reference patterns.

**Option A — pymatgen simulated pattern (fastest, no API):**
```python
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.core import Structure

struct = Structure.from_file("structure.cif")
xrd = XRDCalculator(wavelength="CuKa")   # default 1.5406 Å
pattern = xrd.get_pattern(struct)
for pk in pattern.hkls:
    print(f"2θ={pk['2theta']:.2f}° hkl={pk['hkl']} intensity={pk['intensity']:.3f}")
```

**Option B — Materials Project (search-match):**
```python
from mp_api.client import MPRester
with MPRester() as mpr:
    mats = mpr.materials.summary.search(formula="Fe2O3", is_stable=True)
```

**Option C — ICDD/JCPDS card reference:** For lab data, match measured d-spacings against powder-diffraction file (PDF) cards. Each card lists (d, I/I₀, hkl, 2θ). Compare with tolerance typically **Δ2θ ≤ 0.05–0.1°** (lab) or **≤ 0.01°** (synchrotron).

**Workflow:**
1. Extract peak positions (2θ) and intensities (see Integration → spectral-analysis).
2. Compute d-spacings (Bragg, §1).
3. Generate/obtain candidate reference patterns (pymatgen, MP, or ICDD cards).
4. Match: every observed strong peak should have a reference peak within tolerance; no major unexplained reflections.

### 6. Peak indexing (Miller indices hkl)

Index each reflection to (hkl). For a cubic system: `1/d² = (h²+k²+l²)/a²`.

```python
def cubic_hkl(d_obs, a_lattice):
    """Suggest (h,k,l) for a cubic lattice with parameter a (Å)."""
    n2 = (a_lattice / d_obs)**2      # = h²+k²+l²
    return round(n2)

# Au (fcc, a=4.078 Å): d from 2θ=38.1° → n²≈3 → (111)
print(f"h²+k²+l² = {cubic_hkl(2.36, 4.078):.0f}")
```

**Systematic extinction rules (common):**
- **fcc** : all h,k,l even OR all odd (h²+k²+l² = 3,4,8,11,12,...)
- **bcc** : h+k+l even (h²+k²+l² = 2,4,6,8,10,...)
- Missing first allowed peak → check for a different lattice or preferred orientation.

## Common Pitfalls

1. **β (FWHM) in degrees vs radians** — must convert to radians inside Scherrer/WH. The most common error. (β is **rad** in the formula; `numeric_comparator` unit registry handles `°`.)
2. **K factor selection** — 0.9 (sphere) vs 1.0 (cube); must state which. `formula.py` treats 0.9 as canonical → `K=1` reported as `formula_conflict`.
3. **λ source mixing** — Cu Kα (1.5406 Å) vs Co (1.7902 Å) vs Mo (0.71073 Å). Same d gives different 2θ. Always confirm the λ used; never compare 2θ across different λ without converting.
4. **Instrumental broadening uncorrected** — raw FWHM overestimates crystallite size (underestimates 1/D). Use CWH/broadening-corrected FWHM or state raw-instrument assumption.
5. **Strain anisotropy** — WH assumes isotropic strain; real samples are anisotropic → fit is approximate, don't over-trust the intercept/slope on few peaks.
6. **Crystallite ≠ grain** — Scherrer measures coherent domain, not metallographic grain; do not conflate the two in verification claims.
7. **Multiple phases overlap** — deconvolution (peak fitting) needed before measuring single-peak FWHM.

## Integration with our tools

- **`formulas.py`** (claimeai-service/scripts): `detect_formula()` and `check_constant()` already detect **Scherrer**, **Williamson-Hall**, **dislocation**. This skill extends it: add Bragg/d-spacing and phase-ID detection. Call `detect_formula()` first to route a claim to the right workflow.
- **`numeric_comparator.py`**: units registry `°` (degrees), `см²/с`, `м²/с`, `нм`, `Å`. Use for dimensional consistency (e.g. verify ρ in m⁻² matches a claim's unit).
- **`pymatgen` skill**: crystal structures, CIF/POSCAR, Materials Project lookup, simulated XRD patterns (`XRDCalculator`) — for phase ID and peak indexing.
- **`spectral-analysis` skill**: FFT / peak detection on raw diffraction data to extract 2θ positions and FWHM before applying the equations above.

**Recommended pipeline:** spectral-analysis (detect peaks) → this skill (Bragg/Scherrer/WH/dislocation/indexing) → pymatgen (phase ID / structural refinement).

## Reference Values

| System | Crystallite size D | Notes |
|---|---|---|
| Cold-worked metals | 10–100 nm | peak-broadened |
| Annealed metals / powders | 100 nm–µm | instrumental-limited |
| Ceramics / oxides (sintered) | 20–500 nm | |
| Thin films | 5–100 nm | substrate/interface effects |
| Microstrain ε | 10⁻⁴–10⁻³ | isotropic range |
| Dislocation density ρ | 1e12–1e16 m⁻² | metals: cold-worked high |
| Cu Kα λ | 1.5406 Å | most common source |
| Co Kα λ | 1.7902 Å | Fe-bearing samples |
| Mo Kα λ | 0.71073 Å | high-energy lab source |

**Quick sanity checks:**
- d-spacing of a metal/oxide peak is typically **1–3 Å**.
- A claim "crystallite size = 200 nm from Scherrer" on a routine lab pattern is suspect (instrumental-limited).
- Dislocation density quoted without units (m⁻² vs cm⁻²) is under-specified — flag it.
