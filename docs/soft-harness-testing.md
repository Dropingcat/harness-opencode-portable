# Soft harness testing mode

Goal: keep R0 development moving without spending API/subagent rate limit on
every small correction.

The default local loop is deterministic and cheap:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
$env:PYTHONPATH='src'; python -m researcher_core.debt . --json debt-report.json --fail-on none
$env:PYTHONPATH='src'; python -m researcher_core.artifact malina_research_service_fixture.yaml --json artifact-gap-report.json
```

## Harness pattern

Use `researcher_core.harness.TraceAuditor` for tiny black-box checks:

- record immutable input/output traces;
- check invariant violations locally;
- compare observed event types with a reference trace shape;
- keep mutation tests small and finite.

This mirrors sidecar monitoring without Redis/NATS/OS tracing. Heavy external
tracing and subagent review are reserved for release gates or conflicts.

## Bubble/rivulet cases currently covered

- missing output mutation is detected by the trace invariant;
- matched input/output passes;
- late mutation of payload cannot alter the audited snapshot;
- reference trace comparison reports blind spots;
- event vocabulary rejects typos;
- reason codes are checked against config-backed registry;
- canonical JSON rejects non-string mapping keys;
- policy lint fails closed on missing heuristic metadata;
- limits/timeouts are debt findings unless explicitly ignored;
- YAML fixture gaps against target artifact v0.2 are machine-visible.

## Escalation rule

Run subagent review/tester only when:

- a local invariant fails and the fix is ambiguous;
- a micro-slice changes public contracts;
- artifact gap count unexpectedly increases;
- before accepting a larger milestone.
