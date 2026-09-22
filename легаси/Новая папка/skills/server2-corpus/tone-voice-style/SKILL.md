---
name: tone-voice-style
description: Transform text tone, voice, and writing style — formal↔informal, academic↔popular, technical↔plain, persuasive↔neutral. Use when adapting content for different audiences, simplifying technical text, or matching a publication's voice.
category: writing
allowed-tools: [Read, Write, Edit, Bash]
---

# Tone / Voice / Style Transformation

## Overview

Transform the tone, voice, and writing style of existing text without changing its factual content. This skill converts text between style registers: formal↔informal, academic↔popular, technical↔plain, persuasive↔neutral, and maintains voice consistency across a document.

The core principle: **style is a surface transformation — facts, numbers, and meaning must survive intact.** Every rewrite must be verifiable against the source: no information added, none lost, none distorted.

Use this skill when:
- Adapting a manuscript for a different audience (journal → blog, thesis → press release)
- Simplifying technical or scientific text for general readers
- Matching a publication's or brand's voice
- Converting between formal and informal registers
- Removing or adding persuasive framing
- Ensuring a multi-author document reads as one consistent voice

## When NOT to Use

- When the task is to *write new content from scratch* (use `scientific-writing` or `article-writer` instead).
- When the task is fact-checking or verification (use `fact-checker` / `numeric_comparator`).
- When the task is translation between languages (this skill is register transformation within a language).

---

## Workflow 1 — Style Mapping

Before transforming, determine the target style parameters. Map the audience to concrete, measurable parameters — never vague instructions like "make it more formal."

| Audience | Formality | Jargon density | Sentence length | Voice | Hedging | Example register |
|---|---|---|---|---|---|---|
| Peer-reviewed journal | High | High (field terms kept) | Long, complex | Passive preferred | High (may, could, suggests) | Academic |
| University lecture | Medium-high | Medium (define terms) | Medium | Mixed | Medium | Academic-popular |
| Industry report | Medium | Medium (domain terms) | Medium | Active | Low | Technical |
| General public / blog | Low | Low (plain language) | Short | Active | Low | Popular |
| Marketing / sales | Low | Low | Short, punchy | Active, imperative | None | Persuasive |
| Legal / regulatory | Very high | High (fixed terms) | Very long | Passive | None | Formal-legal |
| Internal memo | Medium | Medium | Short-medium | Active | Low | Neutral-formal |

**Decision procedure:**
1. Identify the *source* register (from the table above).
2. Identify the *target* register.
3. List the parameters that differ (formality, jargon, sentence length, voice, hedging).
4. Transform each differing parameter using the rules below.
5. Verify: facts unchanged, meaning preserved.

---

## Workflow 2 — Formal ↔ Informal

### Formal → Informal
- **Contractions:** expand → contract. "It is not possible" → "It isn't possible"; "We have observed" → "We've observed".
- **Phrasal verbs:** replace Latinate verbs with phrasal verbs. "Investigate" → "look into"; "Eliminate" → "get rid of"; "Postpone" → "put off".
- **Vocabulary level:** replace high-register words with common ones. "Utilize" → "use"; "Commence" → "start"; "Sufficient" → "enough"; "Subsequently" → "then".
- **Sentence length:** split long sentences. Break at subordinate clauses.
- **First person:** allow "I/we/you" where formal text used impersonal constructions.
- **Remove nominalizations:** "The implementation of the system was performed" → "We implemented the system".

### Informal → Formal
- **Expand contractions:** "isn't" → "is not"; "we've" → "we have".
- **Replace phrasal verbs** with Latinate verbs: "look into" → "investigate"; "get rid of" → "eliminate".
- **Raise vocabulary level:** "use" → "utilize" (sparingly — avoid over-formalization); "start" → "commence".
- **Use impersonal constructions:** "You should..." → "It is recommended that..."; "We think" → "It is believed".
- **Prefer passive voice** for objectivity (see Workflow 6).
- **Remove colloquialisms, slang, idioms:** "a lot of" → "a substantial number of"; "basically" → "fundamentally".
- **Lengthen sentences** by combining related clauses with subordination.

---

## Workflow 3 — Academic ↔ Popular

### Academic → Popular
- **Jargon → plain language:** define or replace every field term. "Photosynthesis" → "the process plants use to turn sunlight into food". Keep the term only if you define it on first use.
- **Remove hedging** that confuses lay readers: "The data may suggest a potential correlation" → "The data shows a link".
- **Citations:** keep the source but move to a footnote or "according to a 2023 study" phrasing; don't clutter the prose with (Author, 2023) inline.
- **Passive → active:** "The sample was analyzed" → "We analyzed the sample".
- **Concrete over abstract:** replace abstract nouns with concrete examples and analogies.
- **Add narrative structure:** hook, context, payoff — not IMRAD order.

### Popular → Academic
- **Plain language → precise terminology:** "the stuff that makes plants green" → "chlorophyll".
- **Add hedging** where claims need qualification: "shows" → "suggests"; "proves" → "is consistent with".
- **Add citations** for every factual claim.
- **Active → passive** for objectivity.
- **Remove rhetorical flourishes, exclamations, and emotional language.**
- **Restructure** into IMRAD or discipline-standard organization.

---

## Workflow 4 — Technical ↔ Plain

### Technical → Plain (simplify WITHOUT losing accuracy)
The highest-risk transformation. Rules:
1. **Keep the numbers and units intact.** Never round, drop, or "simplify" a figure. "3.7 × 10⁻³ mol/L" stays exact.
2. **Replace jargon with plain equivalents** but keep the technical term in parentheses on first use: "the catalyst (a substance that speeds up a reaction without being used up)".
3. **Use analogies** for mechanisms, but flag them as analogies: "Think of it like a key fitting a lock — but the lock changes shape."
4. **Shorten sentences** but preserve logical connectors (because, therefore, however).
5. **Keep technical names** (chemicals, species, equipment) — don't invent lay synonyms that are wrong.
6. **Never simplify a caveat away.** "This only applies under vacuum" must survive.

### Plain → Technical
- **Replace plain descriptions with precise terms** (only where the term is unambiguous).
- **Add units, precision, and qualifiers.**
- **Remove analogies** or convert them to formal mechanism descriptions.
- **Add field-standard notation and structure.**

---

## Workflow 5 — Persuasive ↔ Neutral

### Persuasive → Neutral
- **Remove bias words:** "revolutionary", "unprecedented", "groundbreaking", "obviously", "clearly", "undeniably".
- **Remove superlatives** unless factually justified: "the best" → "one of the leading".
- **Balance framing:** present both sides; replace one-sided claims with "X, while Y".
- **Remove calls to action (CTAs):** "Buy now", "Sign up today", "Don't miss out".
- **Replace emotive language** with factual description: "devastating" → "significant".
- **Add hedging** where the source overclaims: "guarantees" → "is designed to".

### Neutral → Persuasive
- **Add benefit framing:** connect features to outcomes.
- **Use active, imperative verbs** for CTAs.
- **Add selective emphasis** (only where factually defensible).
- **Shorten sentences** for rhythm and impact.
- **Add a clear call to action** at the end.

---

## Workflow 6 — Voice Consistency

Maintain a single consistent voice across a document (especially multi-author or merged text).

- **Person:** pick first person ("we"), second ("you"), or third ("the team") and keep it throughout. Don't mix "we analyzed" and "the researchers analyzed" for the same author.
- **Active vs passive:** pick a dominant mode. Scientific = passive; blog = active. Don't flip per paragraph.
- **Tense:** keep narrative tense consistent (past for methods/results, present for established facts).
- **Register:** one formality level throughout — don't drop into slang in one section and formal in another.
- **Terminology:** use the same term for the same concept everywhere ("catalyst" not "catalyst/agent/accelerator" interchangeably).
- **Audit:** after merging, scan for person/tense/register shifts and normalize.

---

## Examples

### Example 1 — Technical → Plain

**Technical (source):**
> The heterogeneous catalyst, comprising palladium nanoparticles immobilized on a mesoporous silica support, facilitates the hydrogenation of unsaturated hydrocarbons at ambient pressure, achieving a turnover frequency of 1.2 × 10³ h⁻¹.

**Plain (target):**
> A catalyst made of tiny palladium particles attached to a porous silica material speeds up the hydrogenation of unsaturated hydrocarbons (the addition of hydrogen to carbon-carbon double bonds) at normal pressure. It processes about 1,200 reactions per hour per active site.

*Note: the number 1.2 × 10³ h⁻¹ is preserved exactly (1,200 per hour); the mechanism is explained; the caveat "at ambient pressure" survives.*

### Example 2 — Academic Abstract → Popular Summary

**Academic (source):**
> The present study investigates the effect of thermal cycling on the phase stability of zirconia-based ceramics. Samples were subjected to 500 thermal cycles between 200 °C and 1200 °C. X-ray diffraction analysis suggests a progressive monoclinic-to-tetragonal phase transformation, which may correlate with microcrack formation and reduced flexural strength.

**Popular (target):**
> We tested how repeated heating and cooling affects a type of ceramic used in high-temperature parts. We heated samples to 1200 °C and cooled them to 200 °C, 500 times. The results suggest the material's crystal structure slowly changes, which can create tiny cracks and make the ceramic weaker.

*Note: numbers (500 cycles, 200–1200 °C) preserved; jargon (monoclinic-to-tetragonal) replaced with "crystal structure changes"; hedging ("suggests", "can") retained to avoid overclaiming.*

---

## Integration

- **scientific-writing** — use Workflow 3 (Academic↔Popular) to adapt manuscripts for lay summaries, press releases, or grant abstracts; use Workflow 6 for multi-author consistency.
- **article-writer** — use Workflow 2 (Formal↔Informal) and Workflow 5 (Persuasive↔Neutral) to match a publication's or brand's voice.
- **documentation-and-adrs** — use Workflow 4 (Technical↔Plain) to make technical docs accessible while keeping accuracy.

---

## Russian vs English Style Conventions

Where the two languages differ, apply these:

- **Contractions:** English uses contractions for informal ("isn't", "we've"). Russian has no written contractions — informality is signaled by word order, particles ("же", "вот", "ну"), and colloquial vocabulary ("сейчас" vs "в настоящее время").
- **Formal markers (RU):** use impersonal constructions ("следует отметить", "было установлено"), passive/reflexive verbs ("рассматривается", "проводится"), and genitive chains. Avoid "мы" in formal academic Russian (use impersonal or "в данной работе").
- **Informal markers (RU):** allow "мы/вы", colloquial particles, shorter sentences, and everyday vocabulary ("много" vs "значительное количество").
- **Jargon (RU):** many technical terms are borrowed (катализатор, дифракция) — keep them but define in plain Russian; avoid unnecessary English loanwords in popular text.
- **Hedging (RU):** "может", "предположительно", "по-видимому" — keep in academic; drop in popular.
- **Persuasive (RU):** imperative forms ("попробуйте", "узнайте") and exclamatory constructions; remove for neutral.
- **Sentence length:** Russian tolerates longer sentences than English; when simplifying to plain Russian, split more aggressively than you would in English.

---

## Common Pitfalls

1. **Losing accuracy when simplifying** — the #1 risk. Always preserve numbers, units, caveats, and qualifiers. Verify the simplified text against the source line-by-line.
2. **Over-simplification** — removing necessary nuance or dumbing down to the point of error. Keep the technical term in parentheses; keep caveats.
3. **Tone inconsistency** — mixing registers within one document. Apply Workflow 6 after any transformation.
4. **Inventing lay synonyms that are wrong** — never replace a technical term with an inaccurate plain word. If unsure, keep the term and define it.
5. **Dropping hedging in academic→popular** — removing all hedging can overclaim. Keep "suggests/can/may" where the evidence is correlational.
6. **Over-formalizing** — "utilize" for "use" everywhere reads as bloated. Formal ≠ wordy; prefer precise, concise formal.
7. **Changing meaning via passive/active flip** — ensure the agent/patient relationship is preserved ("the sample was analyzed" ≠ "the sample analyzed itself").

## Verification Checklist

After any transformation, confirm:
- [ ] All numbers, units, and dates identical to source.
- [ ] All caveats and qualifiers preserved.
- [ ] No facts added, removed, or distorted.
- [ ] Target register parameters met (formality, jargon, sentence length, voice, hedging).
- [ ] Voice consistent across the whole document.
- [ ] Terminology consistent (same term for same concept).
