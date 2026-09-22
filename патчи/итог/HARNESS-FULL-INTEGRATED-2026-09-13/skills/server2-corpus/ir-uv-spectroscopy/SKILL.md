---
name: ir-uv-spectroscopy
description: "Interpret IR and UV-Vis spectra — identify functional groups from infrared peaks, analyze electronic transitions (Beer-Lambert law, band gap via Tauc plot), and run complementary Raman analysis. Use when a researcher or fact-checker needs to verify claims about functional groups, C=O/O-H/N-H stretches, UV absorption maxima, molar absorptivity, or optical band gaps from spectroscopic data. Complements spectral-analysis (FFT/PSD/peak detection), pymatgen (materials/band structure), molecule-visualization (molecular plots), and numeric_comparator (units cm-1, nm, eV)."
---

# IR/UV Spectroscopy Interpretation

## Overview

This skill converts raw IR/UV-Vis spectroscopy data into chemically meaningful interpretation. It covers:

- **IR**: functional-group identification from absorption band positions, fingerprint-region analysis.
- **UV-Vis**: Beer-Lambert quantification, electronic transition classification, Tauc band-gap estimation.
- **Raman**: complementary vibrational analysis (mutual exclusion rule).

It produces numerically grounded, units-aware conclusions that feed into claims for the fact-checker and analysis for the researcher.

## When to Use

- Verifying/claiming a functional group from a reported IR wavenumber (e.g. "carbonyl at 1710 cm⁻¹" → C=O ester).
- Checking a UV-Vis claim (λ_max, extinction coefficient ε, absorbance A vs concentration).
- Estimating an optical band gap (E_g) from absorption/transmittance data (Tauc plot).
- Analyzing an IR fingerprint region to distinguish isomers/polymorphs.
- Cross-checking IR vs Raman complementarity for centrosymmetric molecules.

Do **not** use for full electronic-structure calculations (use `pymatgen`/DFT), mass spectra (use `matchms`/`pyopenms`), or NMR.

## Core Workflows

### 1. IR: Functional group identification (peak → group table)

Read a spectrum as `(wavenumber_cm1[], transmittance_or_absorbance[])`. Identify bands and map to functional groups using the IR reference table below.

```python
import numpy as np

def find_peaks_cm1(x_cm1, y, height=0.05, distance=5):
    """Locate local maxima in an IR absorbance spectrum (numpy-based, no scipy needed)."""
    peaks, = (y > height).nonzero()
    peaks = peaks[np.r_[True, np.diff(peaks) > 1]]
    # refine to local maxima
    idx = []
    for p in peaks:
        win = slice(max(0, p-3), min(len(y), p+4))
        if y[p] == y[win].max():
            idx.append(p)
    return x_cm1[idx], y[idx]

x = np.linspace(400, 4000, 4000)          # cm⁻¹
y = np.exp(-((x-1710)/8)**2) + 0.05*np.random.rand(len(x))
band_pos, band_int = find_peaks_cm1(x, y)
print("IR bands (cm⁻¹):", np.round(band_pos, 0))
```

Map each band to a group with the reference table (§Reference Tables → IR absorption bands).

### 2. IR: Fingerprint region analysis (1500–400 cm⁻¹)

The fingerprint region is rich but hard to assign globally — use it for **matching** and **isomer/polymorph fingerprinting**, not absolute group ID alone.

```python
def fingerprint_similarity(unknown_cm1, unknown_y, ref_cm1, ref_y):
    """Compare two fingerprint spectra on a common wavenumber grid."""
    grid = np.arange(400, 1501, 1.0)
    u = np.interp(grid, unknown_cm1, unknown_y)
    r = np.interp(grid, ref_cm1, ref_y)
    u = (u - u.mean()) / (u.std() + 1e-12)
    r = (r - r.mean()) / (r.std() + 1e-12)
    return float(np.dot(u, r) / len(grid))   # cosine similarity ~ spectral match
```

Use together with symmetric C-H bending/ring modes to narrow down substitution patterns.

### 3. UV-Vis: Beer–Lambert law (A = εcl)

Convert measured absorbance to concentration (or verify a reported ε).

```python
def beer_lambert(A, path_cm=1.0, c_molL=None, eps=None):
    """A = ε·c·l. Provide either c to get ε, or ε to get c.
       Units: A (unitless), c in mol/L, l in cm, ε in L·mol⁻¹·cm⁻¹."""
    if eps is None and c_molL is None:
        raise ValueError("Provide either eps (to get c) or c_molL (to get eps)")
    if eps is None:
        return A / (c_molL * path_cm)          # → ε (L mol⁻¹ cm⁻¹)
    return A / (eps * path_cm)                 # → c (mol/L)

# example: A=0.45, l=1cm, ε=15000 L mol⁻¹ cm⁻¹ → c
print(beer_lambert(0.45, l=1.0, eps=15000))   # ≈ 3.0e-5 mol/L
```

Typical ε: strong π→π* transitions 10⁴–10⁵ L mol⁻¹ cm⁻¹; weak n→π* ~10²–10³; d-d ~10–10².

### 4. UV-Vis: Band gap estimation (Tauc plot)

Convert transmittance/absorbance to absorption coefficient α, then build the Tauc plot.

```python
def absorption_coefficient(A, thickness_m):
    """A = log10(I0/I); α = 2.303·A/d. thickness in meters → α in m⁻¹ (or convert)."""
    return 2.303 * A / thickness_m

def tauc_bandgap(nu_eV, alpha, n=2, fit_range=(1.5, 4.0)):
    """Tauc: (α·hν)^(1/n) vs hν, linear region intercept with energy axis = E_g.
       n=2  (exponent 1/2 → plot (αhν)^2)  for direct band gap.
       n=1/2 (exponent 2  → plot (αhν)^(1/2)) for indirect band gap.
    """
    hv = nu_eV
    y = (alpha * hv) ** (1.0 / n)
    mask = (hv >= fit_range[0]) & (hv <= fit_range[1]) & np.isfinite(y) & (y > 0)
    fit = np.polyfit(hv[mask], y[mask], 1)   # y = a·hv + b
    Eg = -fit[1] / fit[0]                    # intercept on hv axis
    return Eg, fit, hv, y

# example: energy axis (eV) and α in m⁻¹
Eg, *_ = tauc_bandgap(np.linspace(1.5, 4.5, 500), 1e7 * np.exp(-2.4), n=1)
print("Direct band gap ≈", round(Eg, 2), "eV")
```

Conversion shortcuts (also available via `numeric_comparator`):
- E(eV) = 1240 / λ(nm)
- ν̃(cm⁻¹) = 10⁷ / λ(nm)
- λ(nm) = 1240 / E(eV)

### 5. Raman spectroscopy (complementary)

Raman + IR obey the **mutual exclusion rule** for centrosymmetric molecules: a mode Raman-active is IR-inactive and vice versa. Use it to confirm/refute symmetry assignments.

Typical Raman shifts (cm⁻¹): C≡C ~2100–2250, C=C ~1600–1680, C≡N ~2200, aromatic ring ~1000, phenyl ~1600, Si–Si ~300–500.

```python
def check_mutual_exclusion(ir_modes, raman_modes, tol=20):
    """For centrosymmetric systems IR and Raman modes should NOT overlap (within tol)."""
    overlap = [ir for ir in ir_modes if any(abs(ir - r) <= tol for r in raman_modes)]
    return overlap, len(overlap) == 0   # (problematic_overlaps, ok)
```

### 6. Spectral preprocessing (baseline, smoothing, peak picking)

Detrend a slowly varying baseline, smooth noise, then pick peaks.

```python
from scipy import signal

def detrend_baseline(y, width=100):
    """Approximate baseline via moving average / sliding window minimum."""
    baseline = signal.savgol_filter(y, window_length=width if width % 2 == 1 else width + 1, polyorder=1)
    return np.clip(y - baseline, 0, None)

def smooth(y, window=9, poly=3):
    return signal.savgol_filter(y, window_length=window, polyorder=poly)

def peak_pick(x, y, prom=0.02, dist=5):
    """Wrapper around scipy.signal.find_peaks for robust peak picking."""
    p, props = signal.find_peaks(y, prominence=prom, distance=dist)
    return x[p], y[p], props
```

Combine in one preprocessing pipeline for all downstream workflows.

## Reference Tables

### IR absorption bands (functional / structural groups)

| Functional group | Wavenumber range (cm⁻¹) | Notes |
|---|---|---|
| O–H stretch (alcohol/phenol) | 3200–3700 (broad) | H-bond shifts down, broadens |
| N–H stretch | 3300–3500 | primary amine: two bands |
| C–H stretch (sp³) | 2850–2960 | saturated hydrocarbon |
| =C–H stretch (alkene) | 3000–3100 | |
| C≡C–H | ~3300 | terminal alkyne sharp |
| O–H (carboxylic acid) | 2500–3300 (very broad) | overlaps C–H |
| C≡N (nitrile) | 2200–2260 | sharp |
| C≡C (alkyne) | 2100–2260 | |
| C=O (carbonyl) | 1650–1750 | see environment below |
|   – C=O ester | 1735–1750 | |
|   – C=O aldehyde | 1720–1740 | |
|   – C=O ketone | 1705–1725 | |
|   – C=O carboxylic acid | 1700–1725 | |
|   – C=O amide | 1630–1690 | + N–H at 3300 |
| C=C (alkene) | 1620–1680 | |
| C=C (aromatic ring) | 1450–1600 | 2–4 bands |
| N–H bend | 1550–1640 | |
| NO₂ asymmetric | 1520–1600 | |
| NO₂ symmetric | 1345–1385 | |
| C–O (alcohol/ether/ester) | 1000–1300 | |
| C–N | 1000–1350 | |
| S=O | 1300–1350 | |
| C–Cl | 600–800 | |
| C–Br | 500–600 | |
| C–I | 500–600 | |
| fingerprint region | 1500–400 | unique "molecular fingerprint" |

### UV-Vis typical transitions

| Transition type | λ range (nm) | ε (L mol⁻¹ cm⁻¹) | Notes |
|---|---|---|---|
| π→π* | 200–700 | 10⁴–10⁵ | intense, allowed |
| n→π* | 270–330 (typ. 280–300) | 10¹–10³ | weak, "tail" |
| charge transfer (CT) | 400–600 | 10³–10⁴ | metal–ligand / donor–acceptor |
| d→d | 400–800 | 1–10² | weak Laporte-forbidden |
| benzene B-band | 230–270 (fine structure) | 2–4e2 | aromatic |

## Common Pitfalls

1. **Overtones & combination bands**: First C=O overtone ~3400 (≈2×1700) — do not mistake for O–H/N–H.
2. **Fermi resonance**: splitting of otherwise single band (e.g. CO₂ 1380) — report as doublet, not two groups.
3. **Solvent effects**: IR solvents with C–H/O–H absorptions interfere; UV–Vis solvent shifts λmax (polar solvent red/blue shift for n→π).
4. **Baseline drift / sloping baseline**: always detrend before peak-picking or ε quantitation.
5. **Stray light & overabsorbance**: A > 2 saturates; check ε claims are within linear Beer–Lambert range.
6. **Units confusion**: cm⁻¹ vs nm vs eV — always convert (E=1240/λ). A hollow number without units is not a claim.
7. **π vs n transition mis-assignment**: n→π is much weaker and blue-shifted — don't call a weak tail π→π*.
8. **Tauc exponent choice**: direct (n=1) vs indirect (n=1/2) must be justified, or E_g is wrong by 0.1–0.5 eV.
9. **Water interference**: H₂O bends ~1600, broad; avoid false C=O/aromatic conclusions on humid samples.

## Integration with our tools

- `spectral-analysis` — general FFT/PSD/wavelet handling; pass cleaned/processed arrays here for extra analysis.
- `numeric_comparator` — unit registry (cm⁻¹, nm, eV) to validate/conversions in claims; use for pairwise numeric verification of reported peaks/ε.
- `pymatgen` — band structure / DFT gap cross-check for materials; e.g. compare Tauc E_g to computed band gap.
- `molecule-visualization` — render the candidate structure to sanity-check the assigned functional groups.
- `fact-checker` / `researcher` — output claims as (`assignment`, `group`, `wavenumber/λ`, `confidence`, `reference_range`) tuples so downstream can verify.
