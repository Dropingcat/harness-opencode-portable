# Science-Auditor Final Report — exp2b

**Date:** 2026-08-05 20:10  
**Profile:** resercher (science-auditor pilot)  
**Model:** deepseek-v4-flash:cloud  
**Rules:** rules_balanced.yaml  
**Local corpus:** /media/orangepi/1234-5678/AnalisysDataSet/ (794 files)  

---

## Executive Summary

**20/20 claims processed.** After deterministic post-processing:

| Verdict | Count | Details |
|---------|-------|---------|
| **SUPPORTED** | 15 | Claims 1,2,3,6,7,9,11,12,13,14,15,16,17,19,20 |
| **UNSUPPORTED** | 5 | Claims 4,5,8,10,18 |
| **AMBIGUOUS** | 0 | — |
| **Problematic** | 20 | All claims flagged (15 via caveats≥2, 5 via UNSUPPORTED) |
| **Tribunal triggered** | 0 | No critical caveats found |

**Average confidence (pre-process):** 0.905  
**Average confidence (post-process):** 0.85 (SUPPORTED) / 0.50 (UNSUPPORTED)

---

## Detailed Results

### SUPPORTED Claims (15)

| ID | Claim | Conf | Key Caveats |
|----|-------|------|-------------|
| 1 | Nitriding is surface hardening | 1.00 | info: non-ferrous also possible |
| 2 | N diffusion into surface | 1.00 | info: incomplete (also nitride formation) |
| 3 | Nitride formation during nitriding | 0.98 | info: at very low N potential, only solid solution |
| 6 | Holding time depends on depth | 0.95 | info: logical/definitional claim |
| 7 | ε-phase (Fe2-3N) on surface at high N | 0.92 | info: stoichiometry range Fe2N-Fe3N |
| 9 | V nitrides → dispersion hardening | 0.92 | warning: coherency loss reduces effect |
| 11 | XRD confirms ε phase | 0.92 | warning: peak overlap with γ' requires Rietveld |
| 12 | XRD confirms γ' phase | 0.95 | info: generic claim, no specifics |
| 13 | Vickers microhardness 0.1-0.5 N | 0.92 | info: conservative range vs ISO 6507-1 |
| 14 | Measurements on cross-sections after etching | 0.95 | info: standard metallographic practice |
| 15 | Fick's equation for N diffusion | 0.90 | warning: moving boundaries need complex models |
| 16 | Arrhenius law for D(T) | 0.92 | warning: trapping effects in alloyed steels |
| 17 | Ea = 77 kJ/mol for N in α-Fe | 0.95 | info: Callister 76.15 kJ/mol, ~1.1% rounding |
| 19 | Wear resistance ↑ 2-3x | 0.85 | warning: depends on steel grade and test conditions |
| 20 | Dense oxide film after post-oxidation | 0.90 | info: Fe₃O₄ magnetite, 1-2 μm |

### UNSUPPORTED Claims (5)

| ID | Claim | Orig Conf | Reason |
|----|-------|-----------|--------|
| 4 | Nitriding at 500-570°C in NH₃ | 0.85→0.50 | 4 caveats (≥3 → cap 0.5) — upper bound varies (530-650°C), not universal for all nitriding methods |
| 5 | Holding time 10-50 hours | 0.75→0.50 | 3 caveats — salt bath (0.5-4h), deep case (80-160h) excluded |
| 8 | Mo nitrides → dispersion hardening | 0.75→0.50 | 3 caveats — weak nitride former, kinetically delayed, γ=0.4 vs CrN 1.2 |
| 10 | Layer depth 0.3-0.6 mm | 0.92→0.50 | 3 caveats — "standard regime" undefined, varies by steel grade |
| 18 | D₀ = 0.003 cm²/s for N in α-Fe | 0.80→0.50 | 3 caveats — literature shows 10x scatter (0.001-0.01 cm²/s) |

---

## Problematic Theses Analysis

**All 20 claims** were flagged as problematic by the post-processor. This is a known issue with `rules_balanced.yaml`:

- **15 claims** flagged via `caveats_count_gte_2 → mark_problematic` — even definitional claims with 2 info-level caveats are marked problematic
- **5 claims** flagged via `verdict_unsupported` + `confidence_lt_0.6`

**Root cause:** The `caveats_count_gte_2` rule is too aggressive. Definitional claims (1,2,3,6,14,15,16) naturally accumulate 2+ info-level caveats from the physics-advocate step, but these are clarifications, not contradictions.

**Recommendation:** Add a `no_numeric_data` exemption to the caveat-counting rules, or raise the threshold to ≥3 for definitional claims.

---

## Key Findings

### Strongest Claims (confidence ≥ 0.95)
- **Claim 1** (nitriding = surface hardening) — 1.00, textbook definition
- **Claim 3** (nitride formation) — 0.98, fundamental mechanism
- **Claim 12** (XRD γ' phase) — 0.95, well-established methodology
- **Claim 14** (measurements on etched cross-sections) — 0.95, standard practice
- **Claim 17** (Ea = 77 kJ/mol) — 0.95, Callister canonical value

### Weakest Claims (UNSUPPORTED after post-processing)
- **Claim 4** (500-570°C) — 4 caveats, upper bound varies significantly
- **Claim 5** (10-50 hours) — 3 caveats, excludes common shorter/longer processes
- **Claim 8** (Mo nitrides) — 3 caveats, weak nitride former with modest contribution
- **Claim 10** (0.3-0.6 mm) — 3 caveats, "standard regime" undefined
- **Claim 18** (D₀ = 0.003 cm²/s) — 3 caveats, 10x literature scatter

### Numeric Comparison Results
| Claim | Claim Value | Source Value | Deviation |
|-------|-------------|--------------|-----------|
| 4 | 500-570°C | 495-580°C | Minor |
| 5 | 10-50 h | 4-160 h | Captures typical core |
| 10 | 0.3-0.6 mm | 0.2-0.6 mm | No contradiction |
| 13 | 0.1-0.5 N | 0.098-1.961 N | Subset of standard |
| 17 | 77 kJ/mol | 76.15 kJ/mol | ~1.1% |
| 18 | 0.003 cm²/s | 0.003 (Callister) | Exact, but 10x scatter |
| 19 | 2-3x | 2-5x | Conservative |

---

## Questions for Author

1. **Claim 4:** Does the claim refer specifically to gas nitriding or to nitriding in general? Is 570°C from a specific textbook (Lakhtin)?
2. **Claim 5:** Which nitriding method is being referred to? What target case depth?
3. **Claim 8:** What specific Mo nitride phase (Mo₂N vs MoN) and size range? At what minimum Mo concentration?
4. **Claim 10:** Which specific steel grade(s)? What is meant by "стандартный режим"?
5. **Claim 18:** Is the claim for pure α-Fe or a specific steel grade? Which source?
6. **General:** Are all claims intended to describe gas nitriding specifically, or do they cover all nitriding methods?

---

## Recommendations

1. **Fix rules_balanced.yaml:** Add exemption for definitional claims with `no_numeric_data` to avoid false-positive problematic flags
2. **Add context qualifiers:** Claims 4,5,8,10,18 need explicit qualifiers (gas nitriding, specific steel grades, pure α-Fe)
3. **Consider tribunal for Claim 4:** The 570°C upper bound vs 530-565°C from multiple sources warrants deeper investigation
4. **Local corpus search:** The `search_files` tool had path length errors on some queries — consider symlink to shorter path

---

## Files Saved

| File | Path |
|------|------|
| Verdicts (raw) | `/home/orangepi/.hermes/profiles/resercher/workspace/exp2b_20260805_200128/verdicts.json` |
| Verdicts (processed) | `/home/orangepi/.hermes/profiles/resercher/workspace/exp2b_20260805_200128/verdicts_processed.json` |
| Problematic theses | `/home/orangepi/.hermes/profiles/resercher/workspace/exp2b_20260805_200128/problematic_theses.json` |
| Final report | `/home/orangepi/.hermes/profiles/resercher/workspace/exp2b_20260805_200128/final_report.md` |
