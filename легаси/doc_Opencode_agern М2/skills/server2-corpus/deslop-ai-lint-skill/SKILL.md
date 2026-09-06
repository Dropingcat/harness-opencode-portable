---
name: deslop-ai-lint-skill
description: Review text for "AI slop" — the formulaic, hedge-heavy, low-information-density style that machine-generated or AI-assisted writing tends to produce — and either return a structured report of flagged spans or rewrite the text to remove the slop. Use this skill whenever the user asks to check for AI slop, "de-sloppify" or "de-slop" something, flag writing that "sounds AI-generated," review a draft doc/README/commit message/PR description/comment for AI tone, polish a draft before publishing, or tighten prose that feels generic, hedgy, or promotional. Also use it when the user points at a file, paste, or the current conversation context and says something like "clean this up," "make this sound less like an LLM wrote it," or "tighten this." Trigger even if the user does not explicitly say "slop" — any request to review or rewrite textual output for AI tells or generic tone qualifies.
---

# AI Slop Lint

A review-and-rewrite tool for textual artifacts (prose, docs, commit messages, PR descriptions, comments, READMEs). Detects the tonal and structural patterns that signal low-effort AI-generated or AI-assisted writing, explains why each one is a problem, and optionally produces a cleaned-up rewrite.

This skill is **text-only**. It does not analyze code structure, factual correctness, or authorship in a legal sense. Treat the output as a craft signal, not a verdict on who wrote what.

## When to use this skill

Trigger any time the user wants prose evaluated or rewritten for AI-style tells. Examples:

- "Does this README sound AI-generated?"
- "De-slop this commit message."
- "Clean up this draft — feels hedgy and generic."
- "Review this blog intro for tone."
- "Tighten this PR description."
- User pastes a block of text and asks for a rewrite, tone pass, or review.
- User points at a file and asks for a review with AI-slop concerns implied (e.g. "this doc reads like ChatGPT wrote it — help").

Do **not** trigger for:
- Code review or code-quality questions (different skill territory).
- Fiction or creative writing where the user wants an elevated or stylized voice.
- Marketing copy the user has explicitly asked to be hype-heavy or punchy.
- Factuality / hallucination checking — flag template placeholders and obvious refs, but do not verify claims.

## Workflow

1. **Identify the target text.** It may be pasted, quoted, at a file path, or in the recent conversation context. If ambiguous, ask once which block the user wants reviewed.
2. **Identify the user's intent.** Three modes:
   - **Review only** — default if unclear. Produce the findings report (see [Report Format](#report-format)) without rewriting.
   - **Review + rewrite (minimal)** — if the user says "rewrite," "clean up," "de-slop," "tighten," or similar. Preserve meaning, cut the slop. This is the usual ask.
   - **Review + rewrite (aggressive)** — if the user says "aggressive," "rewrite hard," "cut ruthlessly," or similar. Allowed to delete whole sentences/paragraphs (vapid intros, chat sign-offs, disclaimers) rather than paraphrasing them.
3. **Scan the text** against the pattern cheat sheet below. For ambiguous or unfamiliar patterns, consult `references/taxonomy.md` for the full catalog.
4. **Produce the report** using the template in [Report Format](#report-format). Be specific — quote the offending span, name the pattern, say why it's slop, and suggest a fix.
5. **If rewriting**, produce the rewrite after the report as a clean markdown block, then (optionally) a brief "changes made" list for transparency. Present it as a preview — do **not** touch any files yet.
6. **Ask before applying.** After the rewrite block, explicitly ask the user whether they want you to apply it. See [Applying the rewrite](#applying-the-rewrite) for the exact prompts by source type. Never overwrite a file, edit a paste target, or save anything without the user saying "yes, apply it" (or equivalent) in a separate turn.
7. **Close with a handoff note** (see [Handoff note](#handoff-note)). This skill removes the AI-slop smell but does not know the user's house style, brand voice, commit-message convention, doc template, or target audience. Remind the user that the output is de-slopped prose, not yet styled prose — and suggest they run any tone/voice/format skills or workflows of their own on top of it before publishing.

## Pattern cheat sheet

These are the patterns worth memorizing — they cover the majority of real-world cases. Full catalog with detection heuristics and examples lives in `references/taxonomy.md` — read that when a case feels borderline or you need the less common categories.

### Very strong signals (near-definitive AI artifacts)

Flag on sight. These almost never belong in human-edited text.

- **AI self-references**: "As a language model, I…", "As an AI, I cannot…", "As of my last update in 2023/2024/…", "my knowledge cutoff is…".
- **Prompt refusals / capability statements**: "I cannot browse the internet", "I don't have access to real-time data", "I cannot directly edit…".
- **Chat sign-offs in static text** (docs, commits, comments): "I hope this helps", "Let me know if you need anything else", "What would you like me to elaborate on?", "You're absolutely right!", "Great question!".
- **Markdown artifacts in non-Markdown contexts**: raw `**bold**`, `### Heading`, or backticks showing up inside a plain-text commit message, email body, or code comment where Markdown won't render.
- **Tool / citation placeholder traces**: `turn_0_search_0`, `{"source": "tool", "index": 0}`, `access-date=2025-xx-xx`, bracketed citation scaffolds left unfilled.

### Strong signals

- **Mid-sentence questions with canned answers**: "The solution? It's simpler than you think." / "The real challenge? Staying ahead." — short question fragment followed by a glib answer. Very heavy tell in technical prose.
- **Unearned profundity beats**: standalone dramatic sentences like "Something shifted.", "Everything changed.", "But here's the thing.", "And then it hit me." — especially when the surrounding text is neutral or technical.
- **Promotional tone in technical/neutral contexts**: "groundbreaking," "revolutionary," "breathtaking," "dynamic atmosphere," "rich cultural heritage" showing up in a README, RFC, or commit message.
- **Elegant variation**: cycling through near-synonyms to refer to the same thing ("the artist… the creator… the painter…"). Humans reuse the most accurate noun; models avoid repetition too aggressively.

### Moderate signals

Usually worth flagging, but one alone isn't damning — the danger is clusters.

- **Vapid openers**: "In today's fast-paced [landscape/world/ecosystem]…", "As technology continues to evolve…", "In an increasingly interconnected world…", "At the end of the day…".
- **Hedging / importance disclaimers**: "It is important to note that…", "It's worth noting that…", "One must remember that…". Count them — ≥ 3 per 500 words is a smell.
- **Didactic framing**: "In this section, we will explore…", "This article will delve into…", "Let's take a closer look at…" — especially in non-tutorial contexts.
- **AI vocab cluster**: hits from this list appearing together in a short window (roughly 150–200 words, 3+ hits = strong cluster): *delve, delving, tapestry, landscape, realm, ecosystem, intricacies, interplay, synergy, journey, navigate, harness, empower, foster, unlock, leverage, embrace, enhance, underscore, highlight, elevate, revolutionize, pivotal, crucial, transformative, profound, vibrant, dynamic, rich (when abstract), robust, scalable (when decorative)*.
- **Not-X-but-Y rhetorical parallelism**: "It's not X. It's Y.", "This isn't just about X — it's about Y." Fine once; cumulative repetition is a tell.
- **Superficial analysis phrasing**: "This underscores the importance of…", "serves as a powerful reminder that…", "stands as a testament to…", "marks a pivotal moment in the evolving landscape of…" — often attached to no concrete consequence.
- **Mismatched "from X to Y" ranges**: "From the Big Bang to blockchain…", "From cell biology to dark energy…" — sweeping scope without real breadth.
- **Vague attributions**: "Experts say…", "Observers have noted…", "Many believe that…" with no named source.
- **Em dash overload**: em dashes used as catch-all punctuation, more than roughly once per 100 words in non-literary prose.
- **Excessive emoji bullets** in non-marketing contexts (✅ 🚀 💡 as bullet points in a README or RFC).

### Weak signals

Report only when they appear alongside stronger ones.

- Rule-of-three triads ("fast, efficient, and reliable").
- Formulaic conclusions ("In summary…", "In conclusion, this highlights the importance of…").
- Monotonous sentence rhythm / repeated sentence starts ("However," "In addition," "This means" three or more times in a row).
- Title-case headings where sentence-case would be standard.
- Mixed curly and straight quotes.

### Meta-pattern: clusters beat single hits

Any one moderate or weak signal could be legitimate. The confident call comes from **breadth** — multiple categories firing in a short span, especially when a strong signal anchors it. Your report should reflect that: don't over-weight a lone triad.

## Scoring

Assign a **slop score** from 0–100 where **higher = more slop detected**. This is a judgment call informed by counts, not an exact formula — be consistent across reviews but don't fake precision.

The number alone isn't enough — always pair it with a plain-English band label so the user doesn't have to guess what "32" means.

Weights: strong or very strong signal = 3, moderate = 2, weak = 1. Sum, then normalize by document length (roughly: per 500 words). Add bonuses for breadth (3+ distinct categories firing) and for any very strong signal being present at all.

Bands — always report both the number and the band label together:

- **0–20 — Low slop signal.** Reads like careful human prose (or thoroughly edited AI-assisted prose). One or two weak signals at most. No rewrite needed.
- **21–50 — Mixed slop signal.** Some AI-style patterns detectable. A tone pass would help. Rewrite recommended if the user asked for one.
- **51–100 — Strong slop signal.** Clustered slop — likely AI-generated and unedited, or heavily AI-leaning without polish. Rewrite strongly recommended; aggressive mode often appropriate.

A very strong signal alone (e.g. "As a language model, I…" left in the text) should push the score into the Strong band regardless of length.

## Dimensions of slop

Every finding belongs to exactly one of these six dimensions. Use these as the canonical categories in the signal breakdown table (see [Report Format](#report-format)). The taxonomy in `references/taxonomy.md` is organized the same way.

1. **Rhetorical & tonal** — mid-sentence questions, unearned profundity, vapid openers, hedging, didactic framing, promotional tone, forced metaphors.
2. **Vocabulary (AI word cluster)** — overused "AI words" (delve, tapestry, pivotal, ecosystem, harness, embrace, etc.), vague importance inflation, superficial analysis phrasing.
3. **Structural** — monotonous rhythm, excessive lists or emoji bullets, inline bold headings, formulaic conclusions.
4. **Grammar & syntax** — "not X, but Y" parallelism, triads, false "from X to Y" ranges, elegant variation, weasel attributions.
5. **Formatting** — em-dash overload, excessive title-case or bold, Markdown artifacts in non-Markdown contexts, mixed quote styles.
6. **Content-specific** — chat sign-offs, AI self-references, prompt refusals, placeholder data / tool traces, broken references.

## Report format

Use this template. Keep it scannable — this report often gets skimmed, not read. The goal is that a reader sees the score, immediately understands what it means, and can count the damage at a glance before deciding how much attention to give the findings list.

```markdown
## AI Slop Review

**Slop score: <N>/100 — <Low | Mixed | Strong> slop signal.**
*(Higher = more slop. Bands: 0–20 Low, 21–50 Mixed, 51–100 Strong.)*

**Verdict:** <1–2 sentences. What kind of slop this is, the dominant pattern, whether a rewrite is recommended, and if so which mode.>

### Signal breakdown

| Dimension | Detected | Severity mix | Addressed in rewrite |
|---|---|---|---|
| Rhetorical & tonal | <count> | <e.g. 1 Strong, 2 Moderate> | <fixed>/<count> |
| Vocabulary (AI word cluster) | <count> | <...> | <fixed>/<count> |
| Structural | <count> | <...> | <fixed>/<count> |
| Grammar & syntax | <count> | <...> | <fixed>/<count> |
| Formatting | <count> | <...> | <fixed>/<count> |
| Content-specific (chat paste, AI refs, placeholders) | <count> | <...> | <fixed>/<count> |
| **Total** | **<sum>** | — | **<fixed>/<sum>** |

Omit rows for dimensions with zero findings — keep the table lean. If review-only mode (no rewrite), leave the rightmost column blank or write "—" in every row.

### Findings

| # | Span (quoted) | Dimension | Severity | Suggested action |
|---|---|---|---|---|
| 1 | "…the exact quote…" | <Rhetorical & tonal / Vocabulary / …> | <Strong / Moderate / Weak> | <Cut / Rewrite as "…" / Keep but review> |
| 2 | … | … | … | … |

### Document-level notes

- <Rhythm, hedge density, sentence-start repetition, em-dash density, structural smells — whichever apply. Skip if nothing to say.>

### Next step

<One short paragraph — the handoff note. See [Handoff note](#handoff-note) for what belongs here.>
```

If nothing meaningful fires, say so plainly: "Slop score 8/100 — Low slop signal. No substantive AI-slop patterns detected; a couple of mild hedges noted but nothing worth changing." You can drop the signal breakdown table entirely in the Low case — an empty table is worse than no table. Don't manufacture findings. Even in the Low case, still include the Next step handoff.

The breakdown table exists because a bare number doesn't tell the user *what's wrong*. A reader looking at "32/100 — Mixed slop signal" should be able to glance at the table and see "ah, it's mostly vocabulary and hedging, not structural or content-specific." That framing also makes rewrite progress visible — after a rewrite, the reader can verify every flagged issue was addressed, or see which ones were deliberately left alone.

## Rewriting

When the user asks for a rewrite, produce it **after** the report, under a `### Rewrite` heading. Show the full cleaned text as a single copyable block.

### Minimal mode (default)

Preserve the author's intent, structure, and main claims. Cut filler, replace vague words with specific ones, remove disclaimers, and tighten rhythm. Don't introduce new information or change what's being argued.

Rewrite heuristics by pattern:

- **Mid-sentence questions** → direct statement. *"The solution? It's simpler than you think."* → *"The solution is to cache the response and reuse it."*
- **Vapid opener** → replace with context or cut entirely. *"In today's fast-paced world, observability is crucial."* → *"Observability lets us catch performance regressions before users feel them."*
- **AI vocab cluster** → precise language. *"This pivotal initiative delves into the intricate tapestry of our data ecosystem."* → *"This project defines consistent schemas for our core data pipelines."*
- **Superficial analysis** → concrete consequence. *"This policy underscores the importance of access control."* → *"This policy requires every service to enforce role-based access control."*
- **Chat sign-offs** → delete.
- **AI disclaimers** → replace with a neutral factual statement or delete. *"As a language model, I don't have real-time data."* → *"This doc covers events through November 2024."*
- **Elegant variation** → pick the most accurate noun and use it consistently.
- **Hedging cluster** → drop the hedges; commit to the claim the text is actually making.

### Aggressive mode

All of the above, plus license to delete entire sentences or paragraphs that are pure scaffolding (vapid intros, formulaic conclusions, didactic meta-narration, promotional filler). Rewrite from the content inward — keep what carries information, cut what was there to sound serious.

### After the rewrite

Add a short, optional `#### Changes` bulleted list summarizing the biggest cuts and rewrites. Keep it to 3–6 bullets max — the rewrite itself is the artifact, not the changelog. Then go to [Applying the rewrite](#applying-the-rewrite) and ask the user whether to apply it, before the handoff note.

## Applying the rewrite

The default contract: produce the rewrite as a preview the user can see, then **ask** whether to apply it. Do not edit a file, overwrite a paste target, or save anything without explicit confirmation in a separate turn. A rewrite is a judgment call; the preview-then-confirm pattern keeps the user in the loop on voice and nuance decisions that are hard to undo.

### When the source is a file path

If the user pointed at a file ("review README.md", "de-slop docs/overview.md"):

After the rewrite block and the changes list, ask:

> **Want me to apply this rewrite to `<path>`?** Reply *yes* to overwrite, or tell me what to adjust first (keep a specific paragraph, soften a change, swap a word).

If they confirm: use the Edit or Write tool to apply the full rewrite to the file. Then confirm the write with one short sentence at the file level (e.g. *"Replaced the intro paragraph; the rest of the file is untouched."*).

If they push back on specifics: revise the rewrite based on their feedback, re-present it, and ask again. Don't apply partial changes silently.

### When the source is pasted text or conversation context

If the user pasted the text into the chat (or pointed at "my last message," "that draft above"), there is no file to edit — the preview rewrite is itself the artifact.

After the rewrite block and the changes list, ask:

> **Want me to save this rewrite to a file? If so, where — `<suggested-path>.md` or somewhere else?**

If they name a path: use Write to create the file, then confirm. If they decline or ignore the offer: leave the rewrite in the chat and move on — they can copy it themselves.

### When the user asked for review only

Skip the apply prompt entirely. The user didn't ask for a rewrite, so there's nothing to apply. Go straight from findings to the Next step handoff note.

### Never skip the confirmation

Even if the user's framing seems to imply permission ("de-slop this README and apply it," "just rewrite my commit message"), still produce the rewrite first, show it, and ask. The tiny friction of confirming is worth the safety — a misread of the user's voice preference or a missed technical detail is much worse than one extra turn.

## Handoff note

This skill strips AI-slop smells — vapid openers, AI vocab clusters, chat sign-offs, empty hedges, promotional tone — from the text. It does **not** style the prose for the user's specific context. It doesn't know the user's team voice, brand tone, commit-message convention (Conventional Commits vs. free-form), documentation template, preferred reading level, or target audience. A successful de-slop leaves the prose cleaner and more direct, but still generic — still wearing the neutral "thoughtful editor" register, not the user's own voice or the format their destination expects.

Because of that, every output should end with a short `### Next step` note that tells the user to run their own tone, voice, format, or house-style skills or workflows on top of what this skill produced before publishing. This prevents the failure mode where the user ships a technically de-slopped piece that still doesn't match how their team writes. Keep the note short — one or two sentences. Match the register of the rest of the report.

**Examples of good handoff notes:**

- *"Next step: run this through your team's commit-message style (Conventional Commits, scope prefixes, line-length cap). This rewrite is de-slopped but still generic — it doesn't know your repo's conventions."*
- *"Next step: pass this through your voice/brand skill if you have one. I've removed the AI tells, but the tone is still neutral-editor — not the sharper, punchier register your blog usually uses."*
- *"Next step: check this against your docs template. The rewrite is cleaner prose, but headings and section structure should match whatever your team's doc skeleton expects."*
- *"Next step: no rewrite needed, but if you're still shaping this for a specific audience (an RFC vs. a changelog entry vs. a postmortem), run it through whatever tone/format pass fits the destination."*

**When to skip the handoff note:** never. Even on Low-score reviews where no rewrite happens, add a one-line next-step suggestion. The goal is to consistently set expectations: slop removal ≠ tone-matching.

## Edge cases and things to be careful about

- **Quoted AI output.** If the user is clearly quoting AI output for analysis (e.g. a blog post *about* AI slop, or a screenshot discussion), don't lint the quoted material — lint the surrounding human prose. Ask if it's unclear.
- **Deliberate style.** Triads, em dashes, and even "delve" are legitimate in human writing. Rely on clustering, not single hits. When a lone moderate signal appears in otherwise sharp prose, let it pass or note it as a "style call" rather than a finding.
- **Short texts.** A two-sentence commit message with "I hope this helps" at the end doesn't need a scored report — just say "chat sign-off, delete it" and move on. Match the report weight to the text length.
- **False positives from domain language.** "Ecosystem" in a biology paper isn't slop. "Pivotal" in a hinge mechanism spec isn't slop. Context first, pattern second.
- **Don't double down on clusters.** If five findings are all the same AI vocab cluster, report it once as a single finding with the full list of words, not five separate findings.

## Full taxonomy

For uncommon patterns, detection heuristics, or deeper examples beyond the cheat sheet, read `references/taxonomy.md`. It contains the complete pattern catalog organized by category (rhetorical, vocabulary, structural, syntactic, formatting, content-specific) with per-pattern detection notes. Load it when:

- A passage has a pattern you recognize as slop but can't name cleanly.
- You're unsure about severity for a specific pattern.
- The user asks about the methodology ("why is this slop?").

Worked rewrite examples live in `references/examples.md` — useful when the user wants to see the de-slopping style in action before committing to a full rewrite.
