# Writing Orchestration Process

Use this process when turning a premise, topic, subject, or rough idea into a researched article.

## Goal

Shape the article before researching it. A good article workflow starts by clarifying what the piece is trying to do: reader, stance, vibe, thesis, desired points, and boundaries. Research then serves that direction instead of creating a generic source summary.

> **For scientific/engineering works** (dissertation, monograph, textbook, paper), the target is NOT an essay — it is a **traceable argumentation structure**:
> - Read `${OPENCODE_HARNESS_ROOT}/shared/writer-traceability-contract.md` first.
> - After the task is set and a template is chosen (dissertation/monograph/...), create the **DOM YAML** (`templates/writer-dom-dissertation.yaml`) — the structural file with chapters, sections, and known objects as claims, plus base graphs of known assertions.
> - Each draft paragraph fills the DOM; new claims request sources (never restate without a citation). When a paragraph is complete, run iterative **stylistic synthesis** using reference works from academic sources (which are themselves split into claims and graphs).
> - Traceability and uncertainty are primary — they live in the DOM, not in prose.
>
> **Deterministic tooling (model-agnostic, run these — do not improvise):**
> ```
> # 1. Draft loop: decompose a paragraph, match to DOM, flag new claims needing sources
> python "${OPENCODE_HARNESS_ROOT}/scripts/writer/draft_loop.py" --text <draft.md> --dom <slug>-dom.yaml --paragraph-id PAR-01-01-01 [--ref refs/] [--apply]
> #    --apply fills paragraph.text + appends new claims (needs_source) + draft_log (append-only)
>
> # 2. Traceability gate: PASS/FAIL before handoff (exit 0/1)
> python "${OPENCODE_HARNESS_ROOT}/scripts/writer/citation_trace.py" --text <draft.md> --dom <slug>-dom.yaml [--strict]
> #    FAIL -> fix DOM/text and re-run; never hand off a FAIL
> ```
> Both use the deterministic extractor core (`scripts/writer/extractor/`) for span grounding —
> the LLM proposes claims, the code finds and accepts/rejects them by span.

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

After collecting the three reports, produce a lightweight inline synthesis: flag findings as unanimous / majority / singular, record divergences, and organize the evidence by likely article section. This synthesis does not need the full consensus-report format — it needs to be citation-ready for the article-writer.

Skip research only when the user asks to use provided material or when the piece is explicitly opinion/personal and does not need factual grounding beyond supplied sources.

## Phase 5: Draft

Use `article-writer` to draft or revise. Provide the Writing Brief and the research output. Require the `ai-slop-avoidance` skill and the article-writing process.

The draft should serve the brief, not merely summarize the research.

## Phase 6: Review And Handoff

Before returning the final result, check:

- Does the article answer the central question or support the thesis?
- Does the tone match the chosen vibe?
- Are the user's desired points present?
- Are sources attached to the claims they support?
- Are disagreements and uncertainty preserved where needed?
- Did the article avoid generic AI-style structure and filler?

Return the article with a short note on interpretation, remaining gaps, and useful next revisions.
