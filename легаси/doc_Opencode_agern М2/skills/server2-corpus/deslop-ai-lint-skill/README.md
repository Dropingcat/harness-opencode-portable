# deslop-ai-lint-skill

> *"We are in an asymmetrical war against slop."* — Swyx

A portable skill that reviews text for AI slop (formulaic, odd and generic tones) that AI generates for docs and for some reason falls into by default. This skill will pick up on the tropes, score it and flag the areas, and optionally fix it.

---

## Install

[![Install for Claude Code](https://img.shields.io/badge/Install-Claude%20Code-D97757?style=for-the-badge)](#claude-code) &nbsp; [![Install for Codex CLI](https://img.shields.io/badge/Install-Codex%20CLI-000000?style=for-the-badge)](#codex-cli) &nbsp; [![Use in any LLM](https://img.shields.io/badge/Use%20in-Any%20LLM-2563EB?style=for-the-badge)](#any-llm)

### Claude Code

```bash
git clone https://github.com/shessenauer/deslop-ai-lint-skill.git ~/.claude/skills/deslop-ai-lint-skill
```

Restart Claude Code so the skill is picked up. Then invoke it:

- Slash command: **`/deslop-ai-lint-skill`**
- Natural language: *"de-slop this,"* *"review for AI slop,"* *"clean up this draft,"* *"tighten this README."*

For project-scoped install, clone into `.claude/skills/deslop-ai-lint-skill` inside the repo instead.

### Codex CLI

Codex doesn't have a first-class skills directory, but `SKILL.md` is self-contained. Reference it from your repo's `AGENTS.md`:

```markdown
When reviewing prose for tone or AI-generated feel, follow the instructions
in .claude/skills/deslop-ai-lint-skill/SKILL.md (or wherever you clone the
repo). Use the taxonomy in references/taxonomy.md for borderline cases.
```

### Any LLM

Paste `SKILL.md` as a system prompt and send text to review. Works with any chat-capable model (Claude, GPT, Gemini, Llama, etc). No scripts, no runtime dependencies.

---

## What it does

Given a doc, `.md` file, or pasted snippet (blog post, README, commit message, PR description, etc.):

1. **Scores** the text 0–100 on a slop index (higher = more slop).
2. **Labels** the band — *Low*, *Mixed*, or *Strong* slop signal.
3. **Breaks findings down by dimension** across six categories (rhetorical & tonal / vocabulary / structural / grammar & syntax / formatting / content-specific chat-paste artifacts).
4. **Lists specific spans** with severity and a suggested action for each.
5. **Rewrites** the text (minimal or aggressive mode) and **asks before applying** — no silent edits.
6. **Hands off** with a reminder to run your own voice/tone/format pass. Slop removal ≠ tone-matching.

<details>
<summary><b>What a review looks like</b></summary>

```
## AI Slop Review

**Slop score: 78/100 — Strong slop signal.**
*(Higher = more slop. Bands: 0–20 Low, 21–50 Mixed, 51–100 Strong.)*

**Verdict:** Textbook vapid engineering-blog opener. AI vocab cluster firing on
nearly every line, mid-sentence question with canned answer, didactic "we will
delve into" sign-off. Minimal rewrite strongly recommended.

### Signal breakdown
| Dimension            | Detected | Severity mix       | Addressed |
|---                   |---       |---                 |---        |
| Rhetorical & tonal   | 4        | 1 Strong, 3 Mod.   | 4/4       |
| Vocabulary           | 1        | 1 Strong (cluster) | 1/1       |

### Findings
(per-span table with each quoted span, its dimension, severity, suggested fix)

### Rewrite
(cleaned-up text)

### Next step
Run this through your engineering blog's voice pass before publishing.
```

Then: *"Want me to apply this rewrite to `blog/observability.md`?"* — you say yes, the skill overwrites the file. See `SKILL.md` for the full output contract.

</details>

---

## How it works

No scripts — the skill is pure prose. The model does the pattern matching against a cataloged taxonomy and a scoring rubric.

- **Six dimensions** organize the patterns the skill flags: rhetorical & tonal, vocabulary, structural, grammar & syntax, formatting, content-specific.
- **Three severity levels.** Strong signals are near-definitive (AI disclaimers, chat sign-offs, raw Markdown in plain-text contexts). Moderate signals matter when clustered. Weak signals alone are noise.
- **Two rewrite modes.** *Minimal* preserves meaning and cuts filler. *Aggressive* can delete whole scaffolding paragraphs (vapid intros, formulaic conclusions).
- **Preview, then apply.** Rewrites are shown as previews first and applied only on your explicit "yes."
- **Clustering beats single hits.** A lone "delve" or em dash doesn't trigger a finding — patterns that *cluster* across dimensions do.

Full pattern catalog in `references/taxonomy.md`. Before/after rewrite examples in `references/examples.md`.

---

## Limitations

- **English.** The taxonomy is built on English-language AI tropes; other languages differ.
- **Doesn't check facts.** Slop detection is not the same as hallucination-checking.
- **Doesn't know your voice.** The skill strips slop, not styles prose. Run your own tone/brand/format pass on top.

---

## Repo layout

```
deslop-ai-lint-skill/
├── SKILL.md          # The skill — workflow, scoring, output contract, apply flow
├── references/
│   ├── taxonomy.md   # Full pattern catalog, 6 dimensions, detection heuristics
│   └── examples.md   # Before/after rewrite examples
├── evals/
│   └── evals.json    # Test cases
└── README.md
```

---

## Contributing

Patterns evolve as models change. PRs welcome for:

- New patterns in `references/taxonomy.md` with an example and a severity call.
- Failing cases in `evals/evals.json` where the skill mis-handles real-world prose.
- Refinements to the scoring rubric or output contract in `SKILL.md`.

---

## Credits

Built from existing research on AI-generated text plus hands-on observation of sloppy AI content and code.

**Text-focused research**

- Guo, Charlie. *The Field Guide to AI Slop.* Artificial Ignorance. https://www.ignorance.ai/p/the-field-guide-to-ai-slop
- *Measuring AI "Slop" in Text.* arXiv. https://arxiv.org/html/2509.19163v1
- Wikipedia. *Signs of AI writing.* https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- Drainpipe. *Essential Tools to Detect AI Slop Across All Media.* https://drainpipe.io/the-toolkit-for-truth-essential-tools-to-detect-ai-slop-across-all-media/

**Stylometry and detection**

- *Stylometry recognizes human and LLM-generated texts.* arXiv. https://arxiv.org/html/2507.00838v1
- *Accurately detecting AI text when ChatGPT is told to write like a [human].* PMC. https://pmc.ncbi.nlm.nih.gov/articles/PMC10704924/

**Adjacent work on AI-generated code** (different domain, same mental model — "looks polished, rotates out concrete content for filler")

- Larridin. *What Is AI Slop? Detect & Prevent Low-Quality AI Code.* https://larridin.com/developer-productivity-hub/what-is-ai-slop-detect-prevent-low-quality-ai-code
- Aviator. *How to Avoid AI Code Slop.* https://www.aviator.co/blog/how-to-avoid-ai-code-slop/
- *Stop the Slop: An Internal Guide for Devs.* https://stoptheslop.dev/blog/stop-the-slop-an-internal-guide-for-devs

**My personal observations.** I have seen so much slop at this point... I'm just trying to systematically categorize them and find examples. Boiling down to first principles to avoid just sloppiness all the time for everything made. A decent amount of the content has been personally experienced and then also flagged during deep research to expand the tropes/structures to avoid.

---

## License

MIT. See `LICENSE`.
