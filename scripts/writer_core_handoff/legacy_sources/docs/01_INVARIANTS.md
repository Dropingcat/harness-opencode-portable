# 01. Core Invariants v0.2

1. Truth authority is external to Writer and read-only.
2. Structure, rhetoric, argumentation, epistemics, artifacts, policies, dependencies, execution and forensics are separate bounded contexts.
3. No strength-increasing semantic coercion without admitted derivation.
4. Every factual realization must be traceable to claim/evidence/source version or explicitly marked interpretation/gap.
5. Every content-changing transform passes RTT.
6. Bound factual objects (numbers/formulas/citations/standards) are not free-generated under strict policy.
7. Upstream revision invalidates freshness of all dependent downstream nodes according to typed dependency edges.
8. Raw data is immutable; derived outputs are rebuildable and hashed.
9. Review/style requests cannot override epistemic constraints.
10. No release with unresolved release-blocking blocker.
11. Build output is reproducible from recorded versions or explicitly reports non-reproducible dependencies.
12. OSINT/Forensics cannot mutate Writer/Researcher state and may return inconclusive.
