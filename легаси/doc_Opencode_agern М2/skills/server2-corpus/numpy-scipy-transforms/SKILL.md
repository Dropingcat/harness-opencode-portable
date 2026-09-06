---
name: numpy-scipy-transforms
description: Numerical transforms with numpy/scipy — matrix ops, FFT, integration, interpolation, curve fitting, optimization. Use for signal processing, data fitting, numerical analysis, or when numeric_comparator needs extended math.
category: data-engineering
version: 1.0.0
author: doc_guard
license: MIT
tags: [numpy, scipy, FFT, integration, interpolation, curve-fitting, optimization, linear-algebra, numerical-analysis]
dependencies: ["numpy>=1.24.0", "scipy>=1.11.0", "matplotlib>=3.7.0"]
---

# Numpy/Scipy Transforms

## Overview

Numerical transforms and analysis with numpy/scipy: linear algebra, FFT/spectral, integration, interpolation, curve fitting, and optimization. Bridges raw numeric data to physical interpretation. Complements `numeric_comparator` (units/dimension checking) and `spectral-analysis` (frequency-domain) with the underlying math engine.

## When to Use

- Solving linear systems, eigenproblems, SVD, matrix conditioning
- FFT of XRD patterns, spectra, or time-series (forward/inverse, windowing)
- Numerical integration of heat-capacity curves, rate laws, ODEs
- Interpolating sparse/irregular data onto grids
- Fitting kinetic/thermodynamic models (Arrhenius, Scherrer, etc.)
- Minimizing cost functions, root finding, constrained optimization

## Integration with Other Skills

- **numeric_comparator** — validate units/dimensions of fitted parameters and integration results (e.g. `Ea` in kJ/mol, `K` dimensionless). Use `units.convert` / `units.dimension` before comparing fitted values to literature.
- **spectral-analysis** — for PSD/spectrogram/wavelet depth beyond raw FFT; this skill covers the raw FFT mechanics.
- **statistical-analysis** — statsmodels for confidence intervals, hypothesis tests on fit residuals.
- **sympy** — symbolic verification of analytic integrals/derivatives before numeric evaluation.

## Core Workflows

### 1. Matrix Operations

```python
import numpy as np

A = np.array([[4.0, 7.0], [2.0, 6.0]])
b = np.array([1.0, 3.0])

# Solve A x = b (LU-based, prefer over inv @ b)
x = np.linalg.solve(A, b)

# Eigenvalues / eigenvectors
w, v = np.linalg.eig(A)

# SVD (A = U @ S @ Vh)
U, S, Vh = np.linalg.svd(A)

# Inverse, determinant, condition number
A_inv = np.linalg.inv(A)
det = np.linalg.det(A)
cond = np.linalg.cond(A)          # large => ill-conditioned
```

**Pitfalls:** never compute `inv(A) @ b` — use `solve`. Check `cond(A)`; if `> 1e12` the system is ill-conditioned and results are unreliable. Use `np.linalg.lstsq` for over/under-determined systems.

### 2. FFT & Spectral

```python
import numpy as np
from scipy import signal

fs = 1000.0                      # sample rate (Hz)
t = np.arange(0, 1.0, 1.0 / fs)
x = np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 120 * t)

# Forward FFT
X = np.fft.fft(x)
freqs = np.fft.fftfreq(len(x), d=1.0 / fs)

# One-sided magnitude spectrum (normalize!)
n = len(x)
mag = np.abs(X[: n // 2]) / n
freqs_half = freqs[: n // 2]

# Windowing reduces spectral leakage
win = signal.windows.hann(n)
Xw = np.fft.fft(x * win)
mag_w = np.abs(Xw[: n // 2]) / (n * win.mean())

# Inverse FFT (reconstruct)
x_rec = np.fft.ifft(X).real
```

**Pitfalls:** FFT normalization is the #1 bug — divide by `n` for amplitude, and by `n * win.mean()` when windowed. `fftfreq` gives correct bin frequencies. Zero-padding (`np.fft.fft(x, n=2**k)`) interpolates the spectrum but does NOT add resolution. For XRD patterns, convert 2θ to d-spacing via Bragg's law before interpreting peaks.

### 3. Integration

```python
import numpy as np
from scipy import integrate

# Definite integral of a callable (adaptive quadrature)
val, err = integrate.quad(lambda x: x**2, 0, 1)   # 1/3

# Discrete data (trapezoid / Simpson)
x = np.linspace(0, 1, 100)
y = x**2
trap = integrate.trapezoid(y, x)
simp = integrate.simpson(y, x)

# ODE initial value problem
def rhs(t, y):
    return -0.5 * y
sol = integrate.solve_ivp(rhs, (0, 10), [1.0], method="RK45", rtol=1e-8)
t_ode, y_ode = sol.t, sol.y[0]

# Stiff systems: use method="Radau" or "BDF"
```

**Pitfalls:** `quad` returns `(value, error)` — check the error estimate. For discrete data prefer `simpson` over `trapezoid` for smooth curves. `solve_ivp` needs `rtol`/`atol` for accuracy; stiff problems require `Radau`/`BDF`. Integrate heat-capacity curves `∫Cp dT` to get enthalpy — keep units consistent (J vs kJ).

### 4. Interpolation

```python
import numpy as np
from scipy import interpolate

x = np.array([0, 1, 2, 3, 4])
y = np.array([0, 1, 4, 9, 16])

# 1D linear / cubic spline
f_lin = interpolate.interp1d(x, y, kind="linear", fill_value="extrapolate")
f_cub = interpolate.interp1d(x, y, kind="cubic")

# Smooth spline (k=3) with explicit knots
tck = interpolate.splrep(x, y, s=0)
y_smooth = interpolate.splev(np.linspace(0, 4, 50), tck)

# Irregular scattered data -> regular grid
pts = np.random.rand(50, 2) * 4
vals = np.sin(pts[:, 0]) + np.cos(pts[:, 1])
grid_x, grid_y = np.mgrid[0:4:50j, 0:4:50j]
grid_z = interpolate.griddata(pts, vals, (grid_x, grid_y), method="cubic")

# Regular grid interpolator (fast, n-dimensional)
xi = np.linspace(0, 4, 5)
yi = np.linspace(0, 4, 5)
zi = np.random.rand(5, 5)
rgi = interpolate.RegularGridInterpolator((xi, yi), zi)
```

**Pitfalls:** `interp1d` default raises on out-of-range — set `fill_value="extrapolate"` only if physically justified. Cubic splines overshoot near sharp gradients (Runge phenomenon). `griddata` with `method="cubic"` is slow on large data — use `"linear"` or `"nearest"` for big sets.

### 5. Curve Fitting

```python
import numpy as np
from scipy import optimize

# Arrhenius: k = A * exp(-Ea / (R*T))
def arrhenius(T, A, Ea):
    R = 8.314462618  # J/(mol*K)
    return A * np.exp(-Ea / (R * T))

T = np.array([300, 320, 340, 360, 380])
k = np.array([1.2e-3, 3.1e-3, 7.4e-3, 1.6e-2, 3.3e-2])

# curve_fit (Levenberg-Marquardt) with initial guess
popt, pcov = optimize.curve_fit(arrhenius, T, k, p0=[1e6, 5e4])
A_fit, Ea_fit = popt
perr = np.sqrt(np.diag(pcov))     # 1-sigma parameter errors

# Weighted fit (use measurement uncertainties)
k_err = k * 0.05
popt_w, pcov_w = optimize.curve_fit(arrhenius, T, k, p0=[1e6, 5e4],
                                    sigma=k_err, absolute_sigma=True)

# Robust alternative: least_squares with loss="soft_l1"
res = optimize.least_squares(
    lambda p: (arrhenius(T, *p) - k) / k_err, x0=[1e6, 5e4], loss="soft_l1")
```

**Pitfalls:** always provide `p0` — LM is local and sensitive to initialization. Check `pcov` for huge diagonal values (over-parameterized / degenerate model). For Arrhenius, fit `ln(k)` vs `1/T` (linearized) for a robust first guess, then refine with `curve_fit`. Report `Ea` with units (J/mol or kJ/mol) and pass through `numeric_comparator` to validate against literature.

### 6. Optimization

```python
import numpy as np
from scipy import optimize

# Unconstrained minimization (BFGS — smooth, Nelder-Mead — derivative-free)
def rosen(x):
    return (1 - x[0])**2 + 100 * (x[1] - x[0]**2)**2

res_bfgs = optimize.minimize(rosen, [0, 0], method="BFGS")
res_nm = optimize.minimize(rosen, [0, 0], method="Nelder-Mead")

# Bounded optimization
res_b = optimize.minimize(rosen, [0, 0], method="L-BFGS-B",
                          bounds=[(-5, 5), (-5, 5)])

# Root finding (scalar and system)
root = optimize.root_scalar(lambda x: x**2 - 2, bracket=[0, 2])
roots = optimize.root(lambda p: [p[0]**2 - 2, p[1]**3 - 3], [1, 1]).x

# Linear programming (linprog): minimize c^T x s.t. A_ub x <= b_ub
c = [-1, -2]
A_ub = [[1, 1], [2, 1]]
b_ub = [4, 5]
res_lp = optimize.linprog(c, A_ub=A_ub, b_ub=b_ub, method="highs")
```

**Pitfalls:** BFGS needs smooth, differentiable objectives; use Nelder-Mead for noisy/black-box. Always check `res.success` and `res.message`. `linprog` with `method="highs"` is the modern robust default. For multi-start robustness, run `minimize` from several `x0` and keep the best.

## Common Pitfalls (Summary)

1. **Numerical instability** — check `np.linalg.cond`; prefer `solve`/`lstsq` over `inv`.
2. **Ill-conditioned matrices** — results lose significant digits; use SVD-based pseudo-inverse.
3. **FFT normalization** — divide by `n` (and `win.mean()` when windowed); use `fftfreq` for bins.
4. **Integration tolerances** — check `quad` error; set `rtol`/`atol` in `solve_ivp`; use `Radau`/`BDF` for stiff.
5. **Interpolation overshoot** — cubic splines overshoot near gradients; extrapolate only when justified.
6. **Fit initialization** — always give `p0`; linearize first (e.g. Arrhenius `ln k` vs `1/T`).
7. **Units** — keep units consistent through transforms; validate fitted constants with `numeric_comparator`.

## Worked Examples

### Fit Arrhenius data (curve_fit)
See Workflow 5. Fit `A` and `Ea`, report `Ea` in kJ/mol, validate against literature via `numeric_comparator`.

### FFT of an XRD pattern
```python
import numpy as np
two_theta = np.linspace(10, 90, 4000)
intensity = np.exp(-((two_theta - 38.2) / 0.5)**2)  # synthetic peak
X = np.fft.fft(intensity - intensity.mean())
freqs = np.fft.fftfreq(len(intensity), d=(two_theta[1] - two_theta[0]))
# High-frequency components = noise; low-pass to denoise, then inverse FFT
```

### Integrate heat-capacity curve
```python
import numpy as np
from scipy import integrate
T = np.linspace(298, 1200, 200)
Cp = 25.0 + 0.01 * T + 5e-6 * T**2   # J/(mol*K), synthetic
H = integrate.simpson(Cp, x=T)        # J/mol
H_kJ = H / 1000.0                      # convert to kJ/mol
```

## References

- numpy.linalg — https://numpy.org/doc/stable/reference/routines.linalg.html
- scipy.fft — https://docs.scipy.org/doc/scipy/reference/fft.html
- scipy.integrate — https://docs.scipy.org/doc/scipy/reference/integrate.html
- scipy.interpolate — https://docs.scipy.org/doc/scipy/reference/interpolate.html
- scipy.optimize — https://docs.scipy.org/doc/scipy/reference/optimize.html
