# 11. Migration from writer-core R0/SLAW

## Semantic changes

1. Split old nested claim model into Document Tree + read-only Epistemic Projection + Argument/Discourse graphs.
2. Split `epistemic_argument` into separate epistemic and argument contexts.
3. Move runtime authority to SQLite/event log; YAML remains static program/config and fixtures.
4. Replace overloaded unit status with lifecycle, generation, validation, review, publication and freshness axes.
5. Introduce stable object registries for quantity/formula/term/artifact/citation.
6. Replace free writer_context list with typed WritingContract.
7. Add RTT gate before semantic commit.
8. Add dependency invalidation and Blocker entities.
9. Add quantitative/artifact/release subsystems before corpus learning.
10. Add OSINT/Forensics as separate analytical subsystem, never Writer truth.

## Migration strategy

- build adapters from existing WriterUnit and current researcher `writer_context`;
- shadow-write new IR while legacy pipeline remains authoritative;
- compare outputs/diagnostics on golden fixtures;
- switch authority only after M1;
- preserve legacy snapshots as immutable import evidence;
- do not attempt one-shot database rewrite.
