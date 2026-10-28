# Deterministic writer gates

These commands consume the literary DOM described in
`shared/writer-traceability-contract.md`. They never verify scientific truth,
retrieve sources, run research, or modify curated claim/evidence metadata.
Use the existing `WRITER_PYTHON` interpreter (PyYAML is needed for YAML).

```powershell
& $env:WRITER_PYTHON scripts/writer/citation_trace.py --text draft.md --dom dom.yaml --strict
& $env:WRITER_PYTHON scripts/writer/draft_loop.py --text paragraph.txt --dom dom.yaml --paragraph-id PAR-01
# Explicit write, only after the same constraints pass:
& $env:WRITER_PYTHON scripts/writer/draft_loop.py --text paragraph.txt --dom dom.yaml --paragraph-id PAR-01 --apply
```

Both commands print a JSON report; exit 0 means PASS, exit 1 means blocked
(including malformed/missing inputs). `citation_trace.run(text, dom,
strict=False, fail_on='high')` is the review integration. Every real error is
high severity and blocks even without strict mode. Missing derived crossrefs
are warnings; strict mode blocks those too. No scientific curation is inferred
from source presence.

## Accepted conservative text subset

Each prose sentence must express **one exact DOM claim**, carrying `[C-001]`
and one or more corresponding evidence source IDs, e.g.
`The synthetic sample is blue [C-001] [S-001].`
IDs are exact, case-sensitive strings, never positional numbers. Place markers
before terminal punctuation. Multiple sentences are accepted, but each must
independently satisfy grounding. Heading lines must exactly match a DOM chapter
or section title. `[§SEC-01]` must resolve to an exact section ID.

Whitespace and terminal `.?!` are normalized, not meaning or word order.
Unsupported paraphrases, multi-claim sentences, narrative bridges, added causal
statements, and ungrounded prose fail closed rather than receiving invented
semantic approval. This may reject valid scientific prose. For non-established
claims, use a sentence-local prefix `Possibly,`, `Perhaps,`, `Hypothetically,`,
`Возможно,`, `Вероятно,`, `Предположительно,`, or `По-видимому,`.
A marker in another sentence cannot qualify an established assertion.

Claims/sources/chapters/sections/paragraphs are lists of mappings with globally
unique IDs. Claims require text, kind, evidence list, curated verdict and finite
numeric confidence in [0,1]; uncertainty is keyed by claim ID with level
established/inferred/assumed/disputed. Legacy low/medium/high uncertainty is not
silently translated: curate it explicitly first. Duplicate YAML/JSON keys fail.

Evidence requires a source ID and an exact quote plus locator. Supported forms:
`span: 'p.1: «exact quote»'`, `span: {locator: 'p.1', quote: 'exact quote'}`,
or separate `locator` and `quote` fields. A bare `span: conclusions` is not
an exact quotation. When `sources[].text` exists the quote must be its exact
substring. Without source text only quote/locator syntax can be checked; the
report explicitly records this gap. No locator authenticity or quote entailment
is claimed.

Digit-bearing claim text requires an existing researcher numeric comparison
with status MATCH or PARTIAL_MATCH; other/malformed results block. Existing
formula metadata must report `constant_check: formula_consistent`; guard must
be PASS when supplied. Unknown/error/conflicting metadata blocks. No new
numeric or formula algorithm is executed. Curated verdict/confidence/provenance
are consumed unchanged, not promoted by these checks.

## Paragraph ingestion, not autonomous synthesis

`draft_loop` takes a file containing **only the selected paragraph**: no headings,
blank-line-separated blocks, or whole-document positional selection. Its cited
claim set must equal the selected paragraph's existing `claims` list. Missing,
duplicate, unknown or ambiguous IDs fail. It validates the complete DOM and
traces the proposed paragraph before replacing only that paragraph's `text`.
It does not reassign claims or create sources, evidence, causal statements,
verification or uncertainty. It does not perform automatic stylistic rewrites.
If deterministic constrained ingestion is unsafe, it returns the trace/input
reason and leaves files alone. Text input is never rewritten.

Dry-run is default. `--apply` serializes to a same-directory temporary file,
flushes it, checks the original DOM bytes for concurrent changes, then uses
atomic replace. Nonselected/protected fields are preserved as parsed data;
YAML comments, formatting, aliases and JSON whitespace are not preserved.
The byte check is optimistic, not a cross-process transactional lock; avoid
concurrent external editors during apply.

## Synthetic checks

```powershell
$env:WRITER_CORE_ROOT = Join-Path (Get-Location) 'scripts/writer-core'
& $env:WRITER_PYTHON -m unittest discover -s scripts/writer/tests -v
```

Tests select the companion writer directory from `WRITER_CORE_ROOT`, so the
same test file can later exercise a restored original tree. Subprocess review
tests invoke real `wc_cli.py review --dom ...` and actual tracing, never mocks.
