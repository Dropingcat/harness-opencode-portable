# Writing Orchestration Process

Use this process when turning a premise, topic, subject, or rough idea into a researched article.

## Goal

Shape the article before researching it. A good article workflow starts by clarifying what the piece is trying to do: reader, stance, vibe, thesis, desired points, and boundaries. Research then serves that direction instead of creating a generic source summary.

> **For scientific/engineering works** (dissertation, monograph, textbook, paper), the target is NOT an essay — it is a **traceable argumentation structure**:
> - Read `${OPENCODE_HARNESS_ROOT}/shared/writer-traceability-contract.md` first.
> - After the task is set and a template is chosen (dissertation/monograph/...), research and persist `claims.json` plus `writing_contract.json`, then create the **DOM YAML** (`templates/writer-dom-dissertation.yaml`). Never reference these consumer inputs before they exist.
> - Each draft paragraph fills the DOM; new claims request sources (never restate without a citation). When a paragraph is complete, run iterative **stylistic synthesis** using reference works from academic sources (which are themselves split into claims and graphs).
> - Traceability and uncertainty are primary — they live in the DOM, not in prose.
>
> **Deterministic tooling (model-agnostic, run these — do not improvise).** `WRITER_PYTHON`, `WRITER_CORE_ROOT`, and `OPENCODE_HARNESS_ROOT` must be set. The scientific artifact order is research → `claims.json` + `writing_contract.json` → DOM → `verify_claims` → `draft_loop` → RTT/review → `citation_trace`.
>
> PowerShell 5.1:
> ```powershell
> $wc = Join-Path $env:WRITER_CORE_ROOT "wc_cli.py"
> $template = Join-Path $env:OPENCODE_HARNESS_ROOT "templates\writer-dom-dissertation.yaml"
> $verifyClaims = Join-Path $env:OPENCODE_HARNESS_ROOT "scripts\researcher\verify_claims.py"
> $draftLoop = Join-Path $env:OPENCODE_HARNESS_ROOT "scripts\writer\draft_loop.py"
> $citationTrace = Join-Path $env:OPENCODE_HARNESS_ROOT "scripts\writer\citation_trace.py"
> & $env:WRITER_PYTHON $wc plan --topic "<confirmed topic>" --out structure_plan.json
> # Research now persists claims.json and writing_contract.json.
> & $env:WRITER_PYTHON $wc dom --template $template --plan structure_plan.json --claims claims.json --out <slug>-dom.yaml
> & $env:WRITER_PYTHON $verifyClaims --dom <slug>-dom.yaml --apply
> & $env:WRITER_PYTHON $draftLoop --text <draft.md> --dom <slug>-dom.yaml --paragraph-id PAR-01-01-01 --apply
> & $env:WRITER_PYTHON $wc draftcheck --draft <draft.md> --contract writing_contract.json --out rtt_report.json
> & $env:WRITER_PYTHON $wc review --draft <draft.md> --contract writing_contract.json --plan structure_plan.json --dom <slug>-dom.yaml --out review_report.json
> & $env:WRITER_PYTHON $citationTrace --text <draft.md> --dom <slug>-dom.yaml --strict
> ```
>
> POSIX:
> ```sh
> "$WRITER_PYTHON" "$WRITER_CORE_ROOT/wc_cli.py" plan --topic "<confirmed topic>" --out structure_plan.json
> # Research now persists claims.json and writing_contract.json.
> "$WRITER_PYTHON" "$WRITER_CORE_ROOT/wc_cli.py" dom --template "$OPENCODE_HARNESS_ROOT/templates/writer-dom-dissertation.yaml" --plan structure_plan.json --claims claims.json --out <slug>-dom.yaml
> "$WRITER_PYTHON" "$OPENCODE_HARNESS_ROOT/scripts/researcher/verify_claims.py" --dom <slug>-dom.yaml --apply
> "$WRITER_PYTHON" "$OPENCODE_HARNESS_ROOT/scripts/writer/draft_loop.py" --text <draft.md> --dom <slug>-dom.yaml --paragraph-id PAR-01-01-01 --apply
> "$WRITER_PYTHON" "$WRITER_CORE_ROOT/wc_cli.py" draftcheck --draft <draft.md> --contract writing_contract.json --out rtt_report.json
> "$WRITER_PYTHON" "$WRITER_CORE_ROOT/wc_cli.py" review --draft <draft.md> --contract writing_contract.json --plan structure_plan.json --dom <slug>-dom.yaml --out review_report.json
> "$WRITER_PYTHON" "$OPENCODE_HARNESS_ROOT/scripts/writer/citation_trace.py" --text <draft.md> --dom <slug>-dom.yaml --strict
> ```
>
> `--apply` on verification writes verdict/confidence/numeric comparison into DOM claims. A failed trace or review blocks handoff.
> Both use the deterministic extractor core (`scripts/writer/extractor/`) for span grounding —
> the LLM proposes claims, the code finds and accepts/rejects them by span.
> Numeric/guard/formula verification is provided by `scripts/researcher/researcher_core/`
> (verdict + confidence + numeric_comparison are written back to the DOM before drafting).

## Phase 1: Discover Direction

Extract or propose:

- Subject: what the piece is about.
- Tension: why it matters now.
- Audience: who the piece is for.
- Job: inform, persuade, reframe, explain, critique, compare, or provoke.
- Vibe: analytical, sharp, skeptical, explanatory, reported, practical, narrative, contrarian, calm, or another tone.
- Working thesis: the claim or question the piece will organize around.

If the user gives only a topic, brainstorm 3-5 article directions. Each direction should change the thesis, reader, or argument, not just the title.

## Phase 2: Drill Down

Ask targeted questions only where the answer changes the article. Useful prompts:

- Who should feel this was written for them?
- What should the reader believe, understand, or reconsider after reading?
- What point do you already know you want to make?
- What should this piece not become?
- Should the tone be explanatory, skeptical, practical, reported, polemical, or something else?
- How deep should the research go?
- Is this meant to be a publishable article, a working draft, an outline, or a memo?

Prefer one compact question batch. Avoid turning discovery into an endless intake form.

## Phase 3: Confirm The Writing Brief

Before research or drafting, produce a Writing Brief:

- Working title or title direction.
- Audience.
- Vibe.
- Central question or thesis.
- Desired points or ideas.
- Research questions.
- Evidence needs.
- Source priorities or exclusions.
- Out-of-scope items.
- Target format and length.

If the brief involves meaningful tradeoffs, ask for confirmation. If the user gave a complete direction, proceed.

## Phase 4: Research

Research is done by dispatching the built-in `general` sub-agent (single call) via `task`, then synthesizing its report inline. Do not dispatch `synthesizing-researcher` or `researcher-gpt`/`researcher-glm`/`researcher-minimax` — those agent files do not exist (phantoms); the `researcher` agent is disabled.

Use cross-model research when:

- The piece depends on recent facts.
- The claims are contested.
- The article needs examples, numbers, history, or expert views.
- The user asks for high confidence or cross-source validation.

The research prompt should ask for article-useful findings: evidence for claims, counterpoints, examples, caveats, disagreement, and source URLs.

After collecting the report, produce a lightweight inline synthesis: tag confidence, record divergences, and organize the evidence by likely article section. This synthesis does not need a consensus-report format — it needs to be citation-ready for the article-writer.

For scientific/engineering work, research must be completed before DOM assembly when the DOM claims depend on research. Persist two validated artifacts first:

- `claims.json`: stable claim ids, claim text/proposition, source ids, exact evidence spans, kind, and uncertainty.
- `writing_contract.json`: non-empty `{"claims": [...]}` where each entry has at least `claim_id` and `proposition`, and every id resolves to `claims.json`.

Only after both files exist may the process assemble the DOM and run `verify_claims.py --apply`. If research is skipped because the user supplied sources, derive both files from those sources; never fabricate them.

Skip research only when the user asks to use provided material or when the piece is explicitly opinion/personal and does not need factual grounding beyond supplied sources.

## Phase 5: Draft

Use `article-writer` to draft or revise. Provide the Writing Brief and the research output. Require the `ai-slop-avoidance` skill and the article-writing process.

The draft should serve the brief, not merely summarize the research.

When a valid writing contract was supplied or generated, run `wc_cli.py draftcheck` after each material revision and `wc_cli.py review` before handoff. Pass `--plan` only if a plan exists and `--dom` only if a DOM exists. A failed report blocks handoff; an escalated review requires human approval. If no contract exists for an ordinary article, run neither command and report exactly: `Deterministic RTT/review not run: no writing contract was supplied or generated.` These checks supplement rather than replace the scientific `verify_claims.py` → `draft_loop.py` → `citation_trace.py` gates.

## Phase 6: Review And Handoff

Before returning the final result, check:

- Does the article answer the central question or support the thesis?
- Does the tone match the chosen vibe?
- Are the user's desired points present?
- Are sources attached to the claims they support?
- Are disagreements and uncertainty preserved where needed?
- Did the article avoid generic AI-style structure and filler?

Return the article with a short note on interpretation, remaining gaps, and useful next revisions.

## Activation

After changing harness agent or skill contracts, sync the harness skill copies to the live OpenCode config and restart OpenCode so the new environment and prompts are loaded. Live copies under `${OPENCODE_CONFIG_DIR}/skills` are deployment artifacts, not the source edited here.
