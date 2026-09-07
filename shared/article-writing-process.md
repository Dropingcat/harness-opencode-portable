# Article Writing Process

Use this process for articles, essays, explainers, public-facing reports, and substantive prose revisions.

> **For scientific and engineering works** (dissertation, monograph, textbook, paper):
> the primary contract is `${OPENCODE_HARNESS_ROOT}/shared/writer-traceability-contract.md`.
> Traceability and uncertainty live in the DOM YAML (see `templates/writer-dom-dissertation.yaml`),
> NOT in the prose. This process still applies, but the DOM is the source of truth:
> every factual claim in the text must resolve to a claim_id → source + span + verdict.

## Inputs

Start by identifying what the user provided:

- A brief or thesis.
- One or more research reports in the research directory's `reports/` subdirectory.
- Notes in its `notes/` subdirectory.
- URLs or source material.
- An existing draft to revise.

If audience, purpose, format, target length, or publication context would materially change the article, ask a short clarifying question. Otherwise, make a reasonable assumption and state it.

## Workflow

1. Load the `ai-slop-avoidance` skill before drafting or revising.
2. Read the relevant research, notes, sources, or draft.
3. Define the article's central question or thesis in one sentence.
4. Identify the strongest evidence and any real disagreement or uncertainty.
5. Choose a structure that follows the argument, not a stock template.
6. Draft with citations or source references attached to the claims they support.
7. Verify unsupported central claims with `webfetch` or `search`, or remove them.
8. Run the `ai-slop-avoidance` slop audit before handoff.

## Draft Standards

- Open with the actual tension, question, or consequence. Do not use generic throat-clearing.
- Use concrete names, dates, examples, mechanisms, and numbers where the sources support them.
- Attribute analysis to named people, institutions, publications, or studies.
- Keep terminology consistent when precision matters.
- Use tables only when they make comparison easier.
- End by resolving the question, sharpening the implication, or naming what remains uncertain.

## Source Standards

- Every important factual claim needs a source, a clear inference from sources, or an explicit uncertainty caveat.
- Do not cite a URL unless it supports the sentence it is attached to.
- Keep source disagreement visible when it matters.
- Remove tracking parameters and generated citation artifacts unless there is a reason to preserve them.

## Output

For a new article, return:

1. The article title.
2. The article body.
3. A short handoff note with source gaps, slop-audit changes, and persistence status.

For a revision, return:

1. The revised prose or the edited file path.
2. A short summary of the substantive changes.
3. Any remaining verification gaps.
