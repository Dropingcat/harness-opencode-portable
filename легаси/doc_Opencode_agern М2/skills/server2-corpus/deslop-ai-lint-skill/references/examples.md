# Worked De-Slopping Examples

Before/after pairs showing the rewriting style. Read these when the user wants to see the editorial voice, or when you need calibration on how aggressive to be.

---

## Example 1 — Blog intro sandwich (minimal mode)

**Before:**

> In today's fast-paced, increasingly competitive digital landscape, observability has emerged as a pivotal pillar of modern engineering. The real challenge? Building systems that don't just work, but thrive. Organizations that embrace observability unlock the transformative power of their data ecosystem, empowering teams to navigate complexity and deliver truly revolutionary results.

**Findings:**
- Vapid opener ("In today's fast-paced… landscape") — Moderate
- Mid-sentence question with canned answer ("The real challenge? …") — Strong
- AI vocab cluster (pivotal, embrace, unlock, transformative, ecosystem, empower, navigate, revolutionary) — Strong
- Promotional tone — Strong
- Not-X-but-Y parallelism ("don't just work, but thrive") — Moderate

**After:**

> Observability lets engineering teams catch regressions before users feel them. With structured logs, traces, and metrics connected to the same request IDs, a three-hour incident becomes a ten-minute investigation. This post covers the instrumentation we use and the tradeoffs behind each choice.

**Why it's better:** the first sentence now makes a concrete claim (catch regressions before users feel them). The second gives evidence (incident-length reduction). The third orients the reader to what follows. Every AI-vocab word has been replaced or removed.

---

## Example 2 — Chat paste in a commit message (aggressive mode)

**Before:**

```
feat: update user auth flow

I've updated the user authentication flow to use JWT tokens
instead of session cookies. This should improve performance
and scalability.

Key changes:
- ✅ Switched to JWT-based authentication
- ✅ Added token refresh endpoint
- 🚀 Implemented secure storage

As a language model, I don't have the ability to run this code
myself, but the changes should be backward compatible.

I hope this helps! Let me know if you'd like me to elaborate on
any part of the implementation.
```

**Findings:**
- AI disclaimer ("As a language model, I…") — Very Strong
- Chat sign-off ("I hope this helps! Let me know…") — Strong
- Emoji bullets in a commit message — Strong
- Hedging / promotional phrasing ("should improve performance and scalability") — Moderate
- Markdown artifacts in a plain-text context (the bulleted list with emoji renders, but the chat-style closers do not belong) — Strong

**After:**

```
feat(auth): switch from session cookies to JWT

Replaces the cookie-based session flow with JWTs verified on every
request. Adds /auth/refresh for rotating access tokens. Reduces
server-side session storage to zero; measured p99 login latency
dropped from 180ms to 45ms in staging.

Backward compatible: old sessions continue to validate until expiry.
```

**Why it's better:** a real commit message. Emoji bullets gone, disclaimer gone, sign-off gone, vague "should improve" replaced with a measured number. Adds the one piece of context an on-call engineer actually needs (backward compatibility).

---

## Example 3 — Technical doc paragraph (minimal mode)

**Before:**

> It is important to note that when designing a distributed cache, one must remember that consistency and availability are both crucial considerations. In this section, we will delve into the intricate interplay between these two properties, highlighting the key tradeoffs that underscore the importance of careful design. It's worth noting that different systems may require different approaches depending on various factors.

**Findings:**
- Hedging cluster ("It is important to note", "one must remember", "It's worth noting") — Moderate (three hits = strong cluster)
- Didactic framing ("In this section, we will delve into…") — Moderate
- AI vocab cluster (delve, intricate, interplay, key, underscore, importance) — Strong
- Superficial analysis phrasing ("underscore the importance of careful design") — Moderate
- Vague "various factors" attribution — Moderate

**After:**

> Distributed caches force a choice between consistency and availability when a partition happens. This section walks through three tradeoff points: stale reads under leader failure, write amplification from replication, and the recovery cost of rebuilding a cold cache. Different workloads land differently — a read-heavy CDN picks differently from a financial ledger.

**Why it's better:** the hedging is gone, the meta-narration is tightened into a direct outline of what follows, and "various factors" is replaced with two specific contrasting workloads. The technical content is now load-bearing instead of buried under qualifiers.

---

## Example 4 — Short snippet with unearned profundity (minimal mode)

**Before:**

> We migrated the billing service to the new payment provider last month. Something shifted. Everything changed. The team now has a renewed sense of purpose, and we're excited to see where this transformative journey takes us next.

**Findings:**
- Unearned profundity beats ("Something shifted.", "Everything changed.") — Strong
- AI vocab cluster (transformative, journey) — Moderate
- Promotional tone ("renewed sense of purpose", "excited to see where… takes us next") — Moderate
- Formulaic conclusion framing — Weak

**After:**

> We migrated the billing service to the new payment provider last month. Reconciliation time dropped from four hours to twenty minutes, and we deprecated two legacy adapters that had been blocking the settlement rewrite. Next up: retire the old provider's sandbox and wire chargebacks into the same path.

**Why it's better:** the dramatic beats are replaced with actual outcomes (reconciliation time, deprecated adapters). "Where this journey takes us next" becomes a concrete next step (retire sandbox, wire chargebacks). Length is comparable; information density is much higher.

---

## Example 5 — Clean human prose (negative case)

**Before:**

> The migration took three weekends. We split it across two deploys because the schema change needed a backfill pass in between, and the backfill was slow enough that running it during business hours would have pushed read latency past our SLO. In hindsight I'd have sized the database differently going in — we were close to IOPS limits before the backfill and that made the whole window tighter than it should have been.

**Findings:** none substantive. One weak "In hindsight" framing, but paired with a concrete lesson and a specific technical detail (IOPS limits). This is good engineering writing.

**Report:** score **6/100 — Low**. No rewrite needed.

**Why mention this case:** a skill that flags everything becomes noise. Part of the craft is recognizing when prose is tight, specific, and human — and saying so plainly.

---

## Style notes for rewrites

Across all these examples, the moves are the same:

1. **Replace adjectives with evidence.** "Transformative" → a measured outcome. "Crucial" → the consequence of not doing the thing.
2. **Name things.** "The data ecosystem" → "the core pipelines." "Various factors" → the actual factors.
3. **Cut scaffolding.** Intros that announce the topic, conclusions that restate the intro, meta-narration about the document's structure.
4. **Commit to claims.** "It is important to note that X" → just say X.
5. **Match the medium.** Commit messages are plain text and terse. Docs can have structure but shouldn't read like blog posts. Keep the register right.

Rewrite length should usually be shorter than the original, not longer. If your rewrite is longer, question whether you're adding content or just reframing filler.
