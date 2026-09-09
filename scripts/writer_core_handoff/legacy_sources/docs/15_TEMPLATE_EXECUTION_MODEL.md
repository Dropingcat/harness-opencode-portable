# 15. Template Execution Model

## Template != prompt

ExecutablePattern is a versioned declarative program fragment.

Types:
- DocumentPattern
- SectionPattern
- ArgumentPattern
- DiscoursePattern
- ArtifactPattern
- TransformationPattern
- RepairPattern
- ValidationPattern
- ExportPattern

Required fields:

```yaml
id:
version:
kind:
accepts:
preconditions:
slots:
construct:
invariants:
postconditions:
validators:
failure_modes:
provenance:
```

## Pattern lifecycle

```text
OBSERVED_MOTIF
→ CANDIDATE_PATTERN
→ SHADOW
→ EVALUATED
→ PROMOTED
→ DEPRECATED
```

Corpus mining may propose motifs; it cannot auto-promote them into normative templates.

## Reference separation

Reference prose may contribute to:
- style statistics;
- observed discourse/argument motifs;
- examples for humans.

It must not become target factual evidence or be copied as lexical template.

## Template inheritance

Patterns may extend another pattern, but resolved pattern snapshots must be immutable for a build. Conflicting constraints create `POLICY_PATTERN_CONFLICT` Blocker.
