---
name: scientific-writing-hybrid
description: "Universal scientific writing skill that switches between academic (IMRAD, citations, journal submission) and public (essays, explainers, reports) modes based on audience. Combines our article-writer (public prose, source-grounded, ai-slop-avoidance) with openscience scientific-writing (IMRAD structure, citations APA/AMA/Vancouver/IEEE, figures/tables, reporting guidelines CONSORT/STROBE/PRISMA). Use for any scientific text: papers, reports, articles, abstracts, explainers, policy briefs."
category: writing
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Writing (Hybrid)

## Overview

A **universal scientific writing skill** that adapts to the target audience. It merges two complementary writing traditions:

- **Our `article-writer`**: public-facing prose, source-grounded narratives, essays/explainers/reports, explicit **AI-slop avoidance**.
- **OpenAI `scientific-writing`**: rigorous academic manuscripts — IMRAD structure, citation styles, figures/tables, reporting guidelines, two-stage outline→prose process.

**Core principle: choose the mode by audience, not by habit.** The same evidence can be told as a peer-reviewed paper, a technical report, or a public explainer. The skill's job is to detect the audience, pick the right structure and register, and maintain scientific accuracy across every mode.

**Critical Principle for all modes:** write in flowing paragraphs. **Never submit bullet points in the final text.** Use the two-stage process (outline → prose) for every output.

---

## Workflow 1 — Audience Detection

Before writing anything, determine the audience and select the mode. Never guess — look for explicit and contextual signals.

### Detection signals (keywords, context, intent)

| Signal | Academic mode | Technical mode | Public mode |
|---|---|---|---|
| Explicit terms | "manuscript", "paper", "peer review", "journal", "submission", "IMRAD", "reviewer" | "report", "spec", "engineering", "implementation", "practitioner", "build" | "explain", "essay", "explainer", "blog", "for general readers", "summary" |
| Audience named | researchers, scientists, committee | engineers, practitioners, analysts | general public, policy makers, non-specialists |
| Venue | journal, conference, thesis | technical report, documentation, white paper | magazine, blog, newsletter, press release |
| Citation expectation | required, dense | present but lighter | sparse or none (or links/notes) |
| Jargon | field terms kept, defined rarely | domain terms kept | plain language, define everything |
| Abstract | structured/unstructured per venue | executive summary | hook + "what you'll learn" |
| Sentence/voice | passive preferred, hedging | active, direct | active, short, accessible |

### Decision procedure

1. Identify explicit audience/venue signals (from the table above).
2. If ambiguous, ask or choose the **most general** mode that still serves the goal.
3. **Never assume academic** just because the topic is scientific — a blog on a paper is public mode.
4. Confirm the mode once, then apply its template consistently.

**Mode → template mapping:** Academic → IMRAD template; Technical → report template (executive summary + structured sections); Public → narrative template.

---

## Workflow 2 — Academic Mode (IMRAD)

Use for research papers, journal submissions, theses, conference manuscripts, structured reports.

### IMRAD template

- **Introduction**: context → gap → question/hypothesis → significance & novelty.
- **Methods**: design, population, procedures, statistical analysis, ethics. Enough for reproducibility.
- **Results**: findings only, objective, no interpretation; integrate figures/tables.
- **Discussion**: interpret, compare with literature, limitations, implications, future work.
- **Abstract**: 150–300 words, **flowing paragraph(s)** — never labeled sections unless the journal mandates them.
- **Title**: concise, descriptive, keyword-rich.

### Two-stage process (academic)

1. **Stage 1 — Outline**: gather sources, list key points/studies/data as bullets (scaffolding only).
2. **Stage 2 — Prose**: convert every bullet to a full paragraph with transitions and natural citations.

### Reporting guidelines

| Study type | Guideline |
|---|---|
| Randomized controlled trials | CONSORT |
| Observational studies | STROBE |
| Systematic reviews / meta-analyses | PRISMA |
| Diagnostic accuracy | STARD |
| Prediction models | TRIPOD |
| Animal research | ARRIVE |
| Case reports | CARE |

### Citation styles — brief examples

Load `citation-management` for full guides. In-text and reference formats:

- **APA** (author-date, social/behavioral): `(Smith, 2023)` → `Smith, J. (2023). Title. Publisher.`
- **AMA** (numbered superscript, medicine): `result¹` → `1. Smith J. Title. J Sci. 2023;45(2):10-20.`
- **Vancouver** (numbered [brackets], biomed): `result [1]` → `1. Smith J. Title. Journal. 2023;45:10-20.`
- **IEEE** (numbered square brackets, engineering/CS): `result [1]` → `[1] J. Smith, "Title," Journal, vol. 45, pp. 10-20, 2023.`

**Best practices:** cite primary sources; keep recent literature (last 5–10 yr); verify every citation against the original; integrate citations into sentences, never as bare lists.

### Figures and tables

- Tables for exact values; figures for trends/relationships.
- Self-explanatory captions; label all axes/rows/columns with units; note sample sizes; about one display per 1000 words; never duplicate text/data.
- Common types: bar, line, scatter, box, heatmap.

---

## Workflow 3 — Public Mode (article's narrative style)

Write essays, explainers, blog posts, reports, policy briefs for general or policy audiences.

### Narrative template

1. **Hook** — a compelling opening that connects to the reader.
2. **Context** — why it matters, in plain terms.
3. **Core idea** — the main point, explained simply with an analogy or example.
4. **Evidence / explanation** — the actual content, grounded in sources.
5. **Implications / "so what"** — what it means for the reader or policy.
6. **Close** — a clear takeaway or call to thought.

### ai-slop-avoidance (hard rules)

- **Be specific**: real numbers, named studies, concrete examples — never vague "researchers found that…". Give the finding with dates and values.
- **Never hedge-fluff**: avoid "it's important to note that", "it's worth mentioning", filler openers. State it directly.
- **Show, don't summarize**: quote or paraphrase actual evidence; don't gesture at it.
- **No false authorativeness**: if you don't know, say so, or leave it out — do not fabricate.
- **Source-grounded**: every claim traceable to a source; prefer the most authoritative available.
- **Human cadence**: vary sentence length; prefer active voice; read aloud for natural flow.

### Register in public mode

- Define every technical term on first use; keep the term only if essential.
- Prefer short sentences and active voice.
- Use analogies and concrete examples to carry abstract ideas.
- Numbers matter: keep exact figures, but present them readably ("nearly 2 in 3", "a 40% drop" alongside exact values).

---

## Workflow 5 — Two-Stage Process (ALL modes)

Apply this to every mode. Bullet points are planning scaffolding — **never** the final output.

**Stage 1 — Outline.**
Create a structured outline with key points, sources, data, citations. For academic mode use research-lookup/literature-review; for public mode use source-gathering. The outline lists: main arguments, evidence, citations, flow.

**Stage 2 — Prose.**
Convert each bullet to a full paragraph:
1. Expand bullets into complete sentences (subject + verb + object).
2. Add transitions between ideas (however, moreover, in contrast, as a result, in turn).
3. Integrate citations into sentences naturally (academic) or integrate source references naturally (public).
4. Add context that bullets omit.
5. Ensure logical flow and varying sentence structure.

### Verification checklist (both modes)

- ❌ No bullet points remain in the final text.
- ❌ No sentence fragments.
- ✅ Every section reads as connected prose.
- ✅ All facts/numbers unchanged from sources (verifiable).
- ✅ Citation/attribution format matches the mode.

---

## Workflow 5 — Style Switching (across modes, via tone-voice-style)

When you must adapt text between modes (journal → blog, thesis → press release), apply `tone-voice-style` on top of this skill. Keep facts intact — style is a surface transformation.

### Switching tables

| Parameter | Academic | Technical | Public |
|---|---|---|---|
| Formality | High | Medium | Low |
| Jargon | High (field kept) | Medium (domain) | Low (plain) |
| Sentence length | Long | Medium | Short |
| Voice | Passive | Active | Active |
| Hedging | High (may, suggests) | Low | Low |
| Citation density | High | Medium | Low/links |

### Conversion rules (map via tone-voice-style)

- Academic→Public: define jargon, shorten sentences, active voice, reduce hedging, keep numbers.
- Public→Academic: expand, formalize, add citations, lengthen sentences, prefer passive.
- **Accuracy guard**: after any transformation, re-verify numbers, names, dates, and claims against the original — style must never distort facts.

### Citation density by mode

- Academic: full formal citations every claim of evidence.
- Technical: cite key sources, keep numeric rigor.
- Public: cite the most authoritative source (links or a short "Sources" line) rather than heavy in-text citation.

---

## Integration

This skill wires together several existing skills:

- **`scientific-writing`** — academic source: IMRAD, citations, reporting guidelines, figures/tables. Delegate academic detail to it.
- **`article-writer`** — public source: narrative prose, source-grounded, ai-slop-avoidance. Delegate essays/explainers to it.
- **`tone-voice-style`** — for cross-mode style transformation (formal↔informal, academic↔popular).
- **`citation-management`** — full citation styles (APA, AMA, Vancouver, Chicago, IEEE) and reference formatting.
- **`literature-review`** — gather sources for academic and evidence for public mode.
- **`scientific-visualization` / `scientific-schematics`** — figures and technical diagrams.

**Recommendation for a consistent workflow:** (1) detect audience (Workflow 1), (2) pick template (Workflow 2/3), (3) outline (Workflow 4), (4) write prose, (5) style-switch if needed (Workflow 5), (6) verify.

---

## Common Pitfalls

1. **Jargon in public text** — forgetting the audience and leaving technical terms undefined. Fix: define or replace every field term in public mode.
2. **Missing citations in academic** — claims with no source. Fix: cite primary sources for every evidence claim in academic mode.
3. **Bullet points in final prose** — keeping outline scaffolding in the output. Fix: always run Stage 2.
4. **Losing accuracy when simplifying** — dumbing down until facts distort. Fix: keep exact numbers; simplify the explanation, never the data.
5. **Wrong mode chosen** — writing academic for a blog, or simplified for a journal. Fix: explicit audience detection first.
6. **AI-slop in academic** — hedge-fluff, filler, meaningless "comprehensive". Fix: cut fluff, be precise, quantify.
7. **Slippery hedging in public** — over-hedging that confuses readers. Fix: hedge only where genuinely uncertain, and state the confidence.
8. **Inconsistent citation style** — mixing APA/Vancouver. Fix: pick one style and apply throughout.
9. **Passive-voice overuse in academic** — hiding the agent. Fix: use active voice where the actor is clear ("We measured", "The model predicts").

---

## Russian + English Writing Conventions

**English:**
- Academic: prefer impersonal/passive for methods, active for interpretation ("We found that…").
- Use standard scientific English; avoid colloquialisms; consistent US or UK spelling (pick one, state if asked).
- Public: short sentences, active voice, concrete examples, contractions allowed.

**Russian:**
- Academic: formal impersonal constructions common ("было обнаружено", "проведён анализ"); hedge with "предположительно", "может указывать на"; use пассив for methods; active for interpretation ("Мы показали, что…").
- Use scientific Russian: avoid colloquialisms in academic text; keep термины точными; noun-phrase-heavy style is typical ("проведение анализа", "установление зависимости").
- Public: use active voice, plain terms, short sentences; define terms; «около», «почти», «примерно» for readability while keeping exact figures.
- Number & units: Russian decimal comma ("3,5") vs English decimal point ("3.5") — match the document convention. Same for thousand separator.

**Cross-language guard:** never translate and lose precision; technical terms and numbers are the ground truth — adapt only the surrounding register.

---

## Workflow Summary (cheat sheet)

1. **Detect audience** → academic / technical / public.
2. **Pick template** → IMRAD / report / narrative.
3. **Outline** (bullets + sources, scaffolding only).
4. **Write flowing prose** (Stage 2).
5. **Style-switch** via `tone-voice-style` if adapting across modes.
6. **Verify**: facts intact, citations correct, no bullets, register matches audience.
