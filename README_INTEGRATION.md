# Capability Bundle Router Integration Pack

Интеграционный overlay для текущего OpenCode HARNESS, сверенный с `harness.zip` от 2026-09-08.

Он **не заменяет** существующие `routes_authority.json`, `runtime_snapshot.json`, `resolve_route.py`, code-factory, researcher-core или Writer DOM. Он добавляет второй миграционный слой:

```text
request
→ existing resolve_route
→ stage
→ capability requirements
→ live capability preflight
→ minimal logical-tool bundle
→ provider selection
→ bounded capability escalation
→ Job/Attempt/Checkpoint runtime
```

## Что добавляется

### Router

- `config/capabilities_authority.json`
- `config/providers_authority.json`
- `config/stage_capsules_authority.json`
- `config/logical_tools.json`
- `config/job_runtime_policy.json`
- `scripts/router/compile_capability_runtime.py`
- `scripts/router/capability_preflight.py`
- `scripts/router/resolve_bundle.py`
- `scripts/router/capability_escalation.py`

### Tool capsules

- `search_gateway.py` — bounded SearXNG discovery + normalization + SQLite cache.
- `source_resolve.py` — Crossref/OpenAlex/Unpaywall thin resolver.
- `document_inspect.py` — PDF/DOCX/XLSX/TIFF/CSV/text inspection.
- `scientific_image_inspect.py` — TIFF metadata/frames/previews; observational only.
- `science_compute.py` — numeric/symbolic/equation/equivalence/uncertainty/simple chemistry.
- `plot_render.py` — CSV/JSON → deterministic plot artifact.
- `report_compose.py` — report manifest → Markdown artifact.
- `corpus_fts.py` — incremental SQLite FTS5 with hashes, locators and deletion handling.

### Session resilience

- `scripts/jobs/job_ctl.py` — separates stable `job_id`, local `attempt_id`, and external subagent task IDs; stores checkpoints, children, artifacts and gates; rejects parent completion while required children/stages/gates are incomplete.

This formalizes failure patterns present in the current Kanban: timeout/retry, deferred continuation, partial artifacts, parent completion while child tasks can remain nonterminal.

## Core invariants

1. Skill describes how to work. It is not proof that software exists.
2. Logical tool is the stable action vocabulary shown to the LLM.
3. Capability is the physical/runtime requirement.
4. Provider is replaceable implementation: existing MCP, agent, Python, CLI, COM or future service.
5. `implemented != available`. Preflight distinguishes `available`, `degraded`, `missing`, `disabled`.
6. Writer draft/repair does not receive web discovery.
7. Code reviewer does not receive `code.edit`.
8. Search snippets, OCR and extracted text remain observations, not scientific verdicts.
9. Capability escalation is requested by LLM but granted only by deterministic policy.
10. A failed subagent attempt does not automatically mean failed Job.
11. Parent Job cannot complete while required stages/children/gates are incomplete.
12. Existing Stage-1 runtime policy remains authority for top-level route identity during migration.

## Route coverage

Staged bundles are supplied for:

- `academic-research`
- `web-research`
- `writing-prose`
- `document-extraction`
- `code-implementation`
- `code-review`
- `optimization`
- `triz-architecture`

Current `opencode-config`, `service-automation`, and `tech-debt` routes intentionally remain on the existing legacy resolver until their side-effect policies are modeled. `resolve_bundle.py` falls back to legacy behavior for routes without stage definitions.

## Domain overlays

A route stage may be extended with optional domain capabilities without making them unconditional:

- mathematics
- physics / XRD / diffraction
- chemistry
- reports/tables/plots
- Office data
- scientific TIFF/SEM/EDS

Domain overlays do not make a backend available. Preflight still controls provider admission.

## Installation

Dry run first:

```bash
python apply_overlay.py /path/to/HARNESS --dry-run
```

Apply:

```bash
python apply_overlay.py /path/to/HARNESS
```

Existing files with colliding names are copied to:

```text
.overlay_backups/YYYYMMDD-HHMMSS/
```

The current package is additive against the supplied HARNESS, but backup behavior is retained for future versions.

## Required checks after installation

```bash
python scripts/router/compile_runtime.py --check
python scripts/router/compile_capability_runtime.py --check
python scripts/router/capability_preflight.py
python scripts/router/resolve_bundle.py "Найди статьи по XRD и проверь формулы" --route-id academic-research
python -m compileall -q scripts
python -m unittest discover -s tests -p 'test_capability_overlay.py'
python /path/to/overlay/verify_install.py /path/to/HARNESS --output run/capability-install-check.json
```

For researcher-core tests, include its package root:

```bash
PYTHONPATH="$OPENCODE_HARNESS_ROOT/scripts/researcher:$PYTHONPATH" \
python -m unittest discover -s tests/researcher
```

## Capability escalation example

First persist a bundle and preflight snapshot:

```bash
python scripts/router/capability_preflight.py --output run/preflight.json
python scripts/router/resolve_bundle.py \
  "Проанализируй PDF" \
  --route-id academic-research \
  --stage document-analysis \
  --preflight run/preflight.json > run/bundle.json
```

If the agent detects no text layer:

```bash
python scripts/router/capability_escalation.py \
  run/bundle.json document.ocr \
  --reason no_text_layer \
  --preflight run/preflight.json
```

`code.edit` requested from the same stage is denied because it is not declared for that stage.

## Job/checkpoint example

```bash
python scripts/jobs/job_ctl.py --state run/job.json init JOB-1 \
  --contract run/contract.json \
  --stages discovery,source-resolution,document-analysis,evidence-validation,synthesis
```

A timed-out subagent with a checkpoint becomes retryable without losing the Job:

```text
attempt → CHECKPOINT → TIMED_OUT
job → WAITING_RETRY
```

Completed stages and registered artifacts remain in the manifest.

## Dependency policy

The core router layer uses stdlib. Optional tool capabilities probe their own dependencies. Missing optional packages must not prevent HARNESS startup.

See `DEPENDENCY_MATRIX.md` and `requirements-capability-bundle.txt`.

## Integration strategy

This remains a two-snapshot migration seam deliberately:

```text
runtime_snapshot.json              # existing top-level route authority
capability_runtime_snapshot.json   # staged capability/provider authority
```

After live verification on the server, the second authority set can be folded into `runtime_source_manifest.json` and the Stage-1 compiler. Doing that before live verification would mostly improve theoretical elegance while making rollback worse, a familiar trade in software architecture.
