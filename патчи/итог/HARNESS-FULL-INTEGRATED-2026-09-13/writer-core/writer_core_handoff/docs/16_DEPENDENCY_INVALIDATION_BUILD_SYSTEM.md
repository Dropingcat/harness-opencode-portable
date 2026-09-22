# 16. Dependency Invalidation & Semantic Build System

## Freshness is orthogonal to validity

```text
FRESH
STALE
REVERIFY_REQUIRED
REBUILD_REQUIRED
INVALID
```

`STALE` means an upstream dependency changed after last successful validation; it does not assert semantic falsity.

## Dependency examples

```text
RawData → CleanData → Fit → Quantity → Figure → Claim → Paragraph → SectionConclusion → Abstract
SourceVersion → Evidence → Claim → Realization
PolicyVersion → Realization
TemplateVersion → RealizationPlan
TermDefinition → Paragraphs using term
```

## Impact closure

On commit of upstream revision:
1. compute transitive affected closure;
2. apply edge-specific invalidation rule;
3. enqueue only executable downstream work;
4. open blockers when automatic rebuild is forbidden.

## Edge classes

- DATA_DEPENDENCY
- SEMANTIC_DEPENDENCY
- PRESENTATION_DEPENDENCY
- POLICY_DEPENDENCY
- REVIEW_DEPENDENCY
- SOURCE_VERSION_DEPENDENCY

Each edge defines target freshness transition.

## Incremental build invariants

- no downstream entity remains `FRESH` if its dependency revision changed;
- rebuild must not mutate immutable inputs;
- rebuilt artifact gets new revision/hash;
- stale critical claims block release until reverified.
