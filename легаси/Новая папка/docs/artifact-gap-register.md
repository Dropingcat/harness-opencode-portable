# Research artifact gap register

This register keeps documentation debt visible while `malina_research_service_fixture.yaml`
migrates from fixture v0.1 to target `research-service-artifact/0.2`.

Machine check:

```powershell
$env:PYTHONPATH='src'; python -m researcher_core.artifact malina_research_service_fixture.yaml --json artifact-gap-report.json
$env:PYTHONPATH='src'; python -m researcher_core.artifact artifacts/malina_research_service_artifact_target.yaml --fail-on-gap
```

Current controlled gaps:

- Fixture schema is still `research-service-fixture/0.1`, while the target is
  `research-service-artifact/0.2`.
- Claim records still contain legacy `claim_type` and single `status`; target
  shape requires `claim_kind`, `origin_type`, and independent `states.*` axes.
- Some claim records still contain authoritative relation keys such as
  `depends_on`, `derived_from`, `gaps`, and `conflicts`; target shape moves these
  relations to `graph_edges`.
- Target top-level provenance keys `artifact_manifest`, `policy`, and
  `source_versions` are not yet present in the fixture.
- Current machine count from `artifact-gap-report.json`: 97 gaps
  (`high`: 35, `medium`: 62). The increase from 94 happened when the checker was
  aligned with the fuller target top-level artifact shape. Future unexpected
  increases require review.

Acceptance for closing this register:

- `python -m researcher_core.artifact malina_research_service_fixture.yaml --fail-on-gap`
  exits with code 0.
- `artifacts/malina_research_service_artifact_target.yaml` remains a passing
  target-shape reference.
- `python -m researcher_core.debt . --json debt-report.json --fail-on none`
  reports zero findings.
