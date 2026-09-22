# 03. Entity & Graph Registry v0.2

Normative machine registry: `graph_registry.yaml`.

The architecture contains 12 logical graphs/projections: Document Structure, Writing Decomposition, Discourse, Argument, Epistemic Projection, Artifact/Symbol, Citation/Provenance, Policy/Constraint, Revision/Dependency, Execution, Forensics Fingerprint, Work Lineage.

Cross-context links use stable refs; objects do not migrate between ownership domains. In particular:
- Paragraph expresses ClaimRef; it is not a claim.
- ArgumentInstance uses ClaimRef as premise/conclusion; it does not alter claim truth.
- Figure may support/illustrate a claim through an explicit relation and data provenance.
- Forensic profile describes an artifact; it is not author identity truth.

Referential integrity and allowed edge types are schema-validated.
