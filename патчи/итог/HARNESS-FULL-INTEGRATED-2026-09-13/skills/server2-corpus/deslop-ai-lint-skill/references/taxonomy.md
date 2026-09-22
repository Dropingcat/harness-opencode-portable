# AI Slop Taxonomy — Full Pattern Catalog

Reference for cases where the SKILL.md cheat sheet isn't enough. Organized by category. Each entry: what it is, why it smells, how to detect it, how to fix it.

## Contents

1. [Rhetorical and tonal patterns](#1-rhetorical-and-tonal-patterns)
2. [Vocabulary and word-choice tells](#2-vocabulary-and-word-choice-tells)
3. [Structural and architectural patterns](#3-structural-and-architectural-patterns)
4. [Grammar and syntax patterns](#4-grammar-and-syntax-patterns)
5. [Formatting and style tells](#5-formatting-and-style-tells)
6. [Content- and context-specific tells](#6-content--and-context-specific-tells)
7. [Meta-patterns and clusters](#7-meta-patterns-and-clusters)

---

## 1. Rhetorical and tonal patterns

### 1.1 Mid-sentence questions with canned answers — **Strong**

Short question fragment (≤ 5 tokens, ending in `?`) followed by a sentence that answers it.

- "The solution? It's simpler than you think."
- "The real challenge? Staying ahead."
- "The kicker? I never saw it coming."

Heavily overused by LLMs as a high-probability rhetorical template from online articles. Humans use it, but not across every paragraph of a technical doc.

**Detect:** sentence of ≤ 5 tokens ending in `?` followed immediately by a sentence starting with *It/This/The/That/Why/Because*. Strongest signal in neutral prose (docs, RFCs, commits).

**Fix:** collapse into a direct statement. *"The solution? Cache it."* → *"Cache the response and reuse it."*

### 1.2 Unearned profundity / false narrative shifts — **Strong**

Standalone dramatic sentences that announce a turning point without naming what changed.

- "Something shifted."
- "Everything changed."
- "But here's the thing."
- "And then it hit me."
- "Nothing would ever be the same."

Drawn from narrative journalism and inspirational essays; dropped into technical or neutral contexts where there's no stakes.

**Detect:** exact or near-exact match of these phrases as standalone sentences or paragraph openers, with no concrete event or state change described nearby.

**Fix:** delete, or replace with the actual event. *"Everything changed."* → *"We switched from REST to gRPC."*

### 1.3 Vapid openers and transitions — **Moderate**

Generic framing sentences that introduce a topic in abstract, grandiose terms without adding information.

- "As technology continues to evolve…"
- "In today's fast-paced / competitive / digital landscape…"
- "In an increasingly interconnected world…"
- "At the end of the day…"

Safe, broadly applicable, high-probability completions from training data. They delay the real content.

**Detect:** regex at paragraph or document start. Extra suspicious when followed by another generic sentence rather than a concrete claim.

**Fix:** delete and open with the actual claim.

### 1.4 Hedging and importance disclaimers — **Moderate**

Meta-commentary about importance or caution instead of direct statements.

- "It is important to note that…"
- "It's worth noting that…"
- "One must remember that…"
- "Results may vary depending on various factors."

Alignment pushes models toward cautious, non-committal phrasing. In clusters it dilutes clarity.

**Detect:** count hedging phrases per 500 words. 3+ in a short passage is a smell.

**Fix:** drop the hedge; commit to the claim. *"It is important to note that caching improves latency."* → *"Caching improves latency."*

### 1.5 Didactic framing / self-referential narration — **Moderate**

Sentences that describe the structure of the text instead of delivering content.

- "In this section, we will explore…"
- "This article will delve into…"
- "Let's take a closer look at…"
- "Without further ado…"

Common in tutorials and blog posts; adds nothing in technical design docs or comments.

**Detect:** sentence starts with *In this [section/article/post]*, *We will explore/examine/delve*, *Let's take a closer look*.

**Fix:** delete, or convert to a heading.

### 1.6 Promotional / ad-copy tone in technical text — **Strong (in technical contexts)**

Marketing enthusiasm and tourism language appearing in documentation, READMEs, or RFCs.

- "Nestled in the heart of downtown, this venue offers breathtaking views…"
- "This groundbreaking solution will revolutionize the way teams collaborate."
- "With its rich cultural heritage and dynamic atmosphere…"

AI models trained on marketing copy insert promotional language even when the task is neutral description. Almost always inappropriate in engineering contexts.

**Detect:** adjectives like *breathtaking, vibrant, rich cultural, dynamic atmosphere, groundbreaking, revolutionary, seamless, cutting-edge, world-class* in a code/doc context.

**Fix:** replace with a concrete capability. *"groundbreaking caching solution"* → *"cache layer that reduces p99 latency by ~40%"*.

### 1.7 Awkward analogies and forced metaphors — **Moderate**

Elaborate analogies that feel patronizing or out of tone with the surrounding prose.

- "Learning ukulele is like teaching your fingers to dance after years of sitting still."
- "Every chord is a puzzle piece that finally clicks into a song."

LLMs are nudged toward "creative" language and generate metaphors that feel random when the rest of the text is plain.

**Detect:** *"X is like Y"* or *"Think of it as…"* followed by a multi-clause metaphor, especially when surrounded by technical prose.

**Fix:** remove the metaphor, state the idea directly.

---

## 2. Vocabulary and word-choice tells

### 2.1 Overused "AI words" — cluster-based, **Strong / Moderate**

Certain words appear far more often in AI-generated text than in human writing, especially when clustered.

**Verbs:** delve, delving, showcase, harness, empower, foster, unlock, leverage, navigate, embrace, enhance, underscore, highlight, elevate, revolutionize.

**Nouns:** tapestry (abstract), landscape, realm, ecosystem, intricacies, interplay, synergy, journey (abstract), narrative (decorative).

**Adjectives:** pivotal, crucial, key, transformative, profound, vibrant, dynamic, rich (when abstract), robust (overused), scalable (when decorative).

**Detect:** sliding window of roughly 150–200 words. 3+ hits = **strong** cluster. 1–2 hits = **moderate**.

**Fix:** swap each for a plainer, more specific word. "delve into" → "examine" or just the direct claim. "ecosystem" → name the actual set of tools. "pivotal" → "decisive" or drop entirely.

### 2.2 Vague importance / symbolism inflation — **Moderate**

Phrases that assert significance instead of stating concrete effects.

- "This underscores the broader significance of…"
- "serves as a powerful reminder that…"
- "stands as a testament to…"
- "marks a pivotal moment in the evolving landscape of…"

High-probability "serious" phrases used across many corpora; models overuse them to sound weighty without adding content.

**Detect:** verbs *underscores, highlights, serves as, stands as, marks* followed by abstract nouns *significance, importance, broader trend*.

**Fix:** replace with the specific consequence. *"This underscores the importance of idempotency."* → *"Without idempotency, retries corrupt state."*

### 2.3 Superficial analysis phrasing — **Moderate**

Constructions that announce analysis without providing it.

- "This policy underscores its importance, highlighting the need for action."
- "These results illustrate the importance of…" (with no further detail).

**Detect:** verbs *underscores / highlights / illustrates* combined with *importance* and no numbers, examples, or named entities in the same sentence.

**Fix:** add the specific number, example, or entity. If none exists, delete the sentence.

---

## 3. Structural and architectural patterns

### 3.1 Monotonous rhythm and templated structure — **Moderate (document-level)**

Uniform sentence length, repetitive cadence, predictable paragraph structure across a whole document.

**Signals:**
- Low variance in sentence length.
- Many sentences begin with the same 1–3 tokens (*However,*, *In addition,*, *This means*).
- Paragraphs follow a consistent mold: topic restatement → mild elaboration → vague conclusion.

**Detect:** measure sentence-length standard deviation and the share of sentences starting with the same tokens. Report as a document-level note, not a span-level finding.

**Fix:** vary sentence length deliberately. Cut one of the repeated connectors every time you see three in a row. Break the template on at least one paragraph by opening with something other than a restatement.

### 3.2 Excessive lists and emoji bullets — **Moderate / Strong**

Overuse of numbered or bulleted lists and decorative emoji bullets, especially in professional / technical documents.

Models trained on "10 tips" content default to listicles. Sometimes appropriate, but often a tell of AI structure rather than genuine organization.

**Detect:** sequences of many list items where prose would be more natural. Emoji bullets (✅, 🚀, 💡) in non-marketing repos.

**Fix:** convert a list back to prose when the items don't have a natural parallel structure. Remove decorative emoji.

### 3.3 Inline bold headings and outline-style prose — **Moderate**

Bold phrases used as inline headings, or title-case section headers in short documents that don't warrant them.

- "**Key takeaway:** …"
- "**Challenges and Future Outlook**" as a subheading in a short technical note.

**Detect:** bold phrases ending with a colon followed by a sentence; repeated title-case headings in otherwise short documents.

**Fix:** collapse to prose or convert to a real heading with content behind it.

### 3.4 Formulaic conclusions — **Weak**

Standard academic or blog-style conclusion paragraphs that restate the introduction.

- "In summary, the analysis demonstrates the effectiveness of the approach."
- "In conclusion, this highlights the importance of…"

Common in human writing too. Weight only when clustered with other signals.

**Fix:** delete if the document doesn't genuinely need a conclusion; or replace with a concrete next step.

---

## 4. Grammar and syntax patterns

### 4.1 "Not X, but Y" negative parallelism — **Moderate**

Contrastive constructions used as rhetorical flourish rather than genuine clarification.

- "It's not X. It's Y."
- "This isn't just about X — it's about Y."
- "The question isn't whether… it's how."

Heavily used in online essays and thought-leadership; LLMs reproduce it as a catchy structure.

**Detect:** regex on *"not just X, but Y"* and siblings. Weight higher when repeated.

**Fix:** state the positive claim directly. *"It's not about speed, it's about consistency."* → *"Consistency matters more than speed here."*

### 4.2 Rule of three / triads — **Weak**

Three parallel items for emphasis: *"Fast, efficient, and reliable."*, *"Think bigger, act bolder, move faster."*

Legitimate rhetorical device; LLMs over-use because it sounds stylish. Weak alone — only flag when clustered.

### 4.3 False ranges and mixed items — **Moderate**

*"From X to Y"* constructions that mix unrelated items or exaggerate scope.

- "From the Big Bang to blockchain…"
- "From cell biology to dark energy, our journey spans the universe of science."

Trying to sound sweeping without accurate breadth.

**Detect:** *"From [A] to [B]"* where A and B are in distant or mismatched domains.

**Fix:** pick a real range or drop the construction.

### 4.4 Elegant variation — **Strong**

Cycling through synonyms for the same entity instead of reusing a clear term.

- "After the artist completed the work, the creator moved to Paris where the painter established a studio."

AI models avoid repetition too aggressively, producing confusing chains. Humans usually repeat the accurate noun.

**Detect:** within a small window, multiple different near-synonyms referring to the same entity.

**Fix:** pick the most accurate noun and use it consistently.

### 4.5 Vague attributions / weasel words — **Moderate**

Attributions that invoke unnamed groups.

- "Experts say that…"
- "Observers have noted an increasing trend…"
- "Many believe that…"
- "Some critics argue…"

**Detect:** *experts/observers/many/critics + say/argue/believe/note* without a named entity or citation in the same or neighboring sentence.

**Fix:** name the source, or restate as the author's claim.

---

## 5. Formatting and style tells

### 5.1 Em-dash overload — **Moderate**

Em dashes used as catch-all punctuation, more often than typical for the genre.

Example (too many in one sentence): *"Hey, just to clarify — there are multiple countries — and private companies — actively pushing forward commercial space travel for profit."*

**Detect:** em dashes per 1000 tokens compared against baseline for the corpus. Roughly > 1 per 100 words in non-literary prose is high.

**Fix:** convert most em dashes to commas, parentheses, or full stops.

### 5.2 Title-case headers and excessive emphasis — **Weak–Moderate**

Aggressive title-casing, frequent bold/italic, occasional Unicode-bold-style text.

Models borrow formatting from blog / marketing layouts.

**Detect:** proportion of headings in Title Case + density of bold markers.

**Fix:** convert headings to sentence case; remove bold from anything that isn't genuinely the key claim of a paragraph.

### 5.3 Markdown syntax in non-Markdown contexts — **Strong**

Raw Markdown formatting appearing where it won't render.

- `**bold**` or `_italic_` in a commit message.
- `### Heading` inside a code comment.
- Backticks in an email body.

Strong indicator the content was pasted from a chat UI.

**Fix:** strip the Markdown; use whatever emphasis convention the medium actually supports.

### 5.4 Mixed curly and straight quotes — **Weak**

Inconsistent use of smart quotes, especially inside code or data snippets. Style/quality indicator more than an AI-specific signal.

---

## 6. Content- and context-specific tells

### 6.1 Collaborative chat sign-offs — **Strong**

Chatty closing lines belonging to an assistant conversation, not to static text.

- "I hope this helps."
- "Let me know if you need anything else."
- "What would you like me to elaborate on?"
- "You're absolutely right!"
- "Great question!"

Very strong indicator that chat output was pasted directly into a doc, commit, or comment.

**Fix:** delete entirely.

### 6.2 AI disclaimers and knowledge-cutoff references — **Very Strong**

Explicit references to being an AI model or having a knowledge cutoff.

- "As a language model, I…"
- "As an AI, I cannot…"
- "As of my last update in 2023…"
- "my training data only goes up to…"

Should not appear in human-authored docs unless explicitly quoted for analysis. A single hit pushes the slop score into the Strong band.

**Fix:** replace with a neutral factual statement or delete.

### 6.3 Prompt refusals and capability statements — **Very Strong**

Text indicating inability to perform actions typical of chatbots.

- "I cannot directly edit Wikipedia."
- "I don't have access to real-time data."
- "I cannot browse the internet."

Direct evidence of pasted AI output.

**Fix:** delete.

### 6.4 Technical markup artifacts and placeholder data — **Strong**

Internal or placeholder structures leaking into surface text.

- JSON-ish citations or tool traces: `turn_0_search_0`, `{"source": "tool", "index": 0}`.
- Placeholder dates: `access-date=2025-xx-xx`, `2024-01-0x`.
- Citation fields that look templated or incomplete: `[citation needed]` left in, `[[1]]` with no corresponding entry.

**Fix:** replace with real citations / dates, or remove.

### 6.5 Hallucinated or broken references — **Strong**

References that sound plausible but don't resolve.

- DOIs pointing to unrelated articles.
- URLs returning 404.
- Book titles that don't exist.

Known failure mode for AI-generated text. Flag for verification; don't try to verify yourself unless the user asks.

**Fix:** verify each suspicious citation; replace or remove broken ones.

---

## 7. Meta-patterns and clusters

Individual patterns are suggestive, not definitive. The reliable signal is **breadth** — patterns from multiple categories firing in the same passage.

Common slop clusters:

- **The blog intro sandwich**: vapid opener + AI vocab cluster + mid-sentence question + promotional tone.
- **The chat-paste**: Markdown artifacts + chat sign-off + AI disclaimer + capability statement.
- **The empty analysis**: hedging + superficial analysis phrasing + vague attributions + formulaic conclusion.
- **The overstructured doc**: excessive lists + inline bold headings + monotonous rhythm + title-case.

When you see a cluster, name it. The user benefits more from "this has the blog-intro sandwich pattern — cut the opener and the question beat" than from four separate findings.

## Confidence calibration

- A very strong signal alone is near-definitive — report it with high confidence.
- A lone moderate signal is worth flagging but not worth scoring high on.
- A lone weak signal is barely worth mentioning; fold it into a document-level note if anywhere.
- **Confidence should come from clustering**, not from the strongest single hit.

## When in doubt

If a passage triggers your slop sense but nothing on the cheat sheet or this catalog fits cleanly, describe what feels off in plain language — "this paragraph has four sentences of scaffolding before the first concrete claim" is a useful finding even without a named pattern. Don't force every finding into a slot.
