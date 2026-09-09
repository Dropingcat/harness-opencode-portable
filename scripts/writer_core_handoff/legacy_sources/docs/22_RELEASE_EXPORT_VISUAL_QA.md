# 22. Release, Export & Visual QA

## Release candidate gate

Must satisfy:
- zero release-blocking blockers;
- no stale critical claims/artifacts;
- required RTT passes;
- citation entailment/resolution passes;
- quantitative/artifact integrity passes;
- review policy fulfilled;
- no broken cross-references;
- build manifest complete.

## Reproducible BuildManifest

Stores document/claim/data/template/policy/source versions, scripts, model/validator versions and hashes.

## Export verification

DOCX/PDF/MD are parsed back where possible and structurally compared against Document IR:
- headings/order;
- equations/captions;
- cross references;
- tables;
- citations;
- numbering.

## Visual preflight

Page-render QA catches layout failures not visible in semantic IR:
- overflow/clipping;
- orphan heading/caption;
- broken table pagination;
- unreadable figure;
- detached caption;
- equation rendering failure;
- margin/header/footer violations.

## Multi-format divergence

DOCX and PDF are separate build outputs; equivalence diagnostics are recorded. A PDF cannot inherit PASS from DOCX automatically.
