# Future direction — Portable RoleCard / RoleReference / Role Knowledge DOM

Date: 2026-09-13
Status: design-on-growth only; non-authoritative; linked to TD-036/TD-041.

## Goal

The current R4 role model intentionally separates:

- role admission/authority in `TribunalCompositionPolicy`;
- semantic operating guidance in the Role Handbook;
- per-case context in `RoleBriefContract` / `RoleInstructionPack`;
- observed execution history in Job/Attempt + ArgumentArtifact.

A future multi-user/multi-module system should be able to **export, inspect, compare, fork, recombine and exchange role definitions** without collapsing those layers back into one prompt string.

The target is a portable canonical YAML DOM representing a role as a graph-backed object.

## Proposed object family

```text
RoleReference
  stable identity + version + provenance

RoleCard
  human/semantic definition of one role family

RoleParameterGraph
  typed nodes/edges describing competencies, methods,
  evidence expectations, failure modes, question lenses,
  domain compatibility and observed behavior

RoleVariantCard
  first_pass / challenger / cross_exam / defense / ...

RoleEvaluationSnapshot
  benchmark/history projection; never role authority

PortableRoleDOM
  exchange envelope connecting the above objects
```

## Why a graph, not one role YAML blob

Role properties are not flat. Examples:

```text
XRD_SPECIALIST
  REQUIRES -> diffraction_method_reasoning
  EXPECTS -> instrumental_reference
  CHECKS -> stress_vs_composition_ambiguity
  SPECIALIZES -> crystallographer
  COMPATIBLE_WITH -> METHOD uncertainty
  MAY_REQUEST -> stress_sensitive_measurement
  FORBIDS -> phase_assignment_without_visible_evidence
```

Different organizations may share the same semantic role while binding different providers/tools under their own authority policies. Therefore the portable role graph must carry semantic/reference information but must not grant runtime rights.

## Role reference capture and recomposition

A future role-builder may ingest a reference role from:

- an existing admitted RoleCard;
- human expert operating procedures;
- benchmarked historical Tribunal behavior;
- a domain handbook;
- an organization-specific role pack.

The system should decompose the reference into typed parameters and edges, preserve provenance, and allow recomposition into a proposed role/variant.

This is analogous to round-trip semantic validation:

```text
reference role
-> extract realized role claims/parameters
-> normalize into RoleParameterGraph
-> compose candidate RoleCard/variant
-> re-extract candidate properties
-> compare against authorized reference constraints
```

Track at least:

- scope drift;
- capability inflation;
- authority leakage;
- missing mandatory checks;
- newly introduced forbidden moves;
- incompatible evidence expectations;
- semantic duplication/equivalence with admitted roles.

## Proposed portable YAML DOM

Illustrative, not yet executable:

```yaml
schema_version: portable-role-dom/0.1-proposal
role_ref:
  id: ROLE:xrd-specialist
  version: 3
  derived_from:
    - ROLE:crystallographer@2
    - HANDBOOK:materials-xrd@5

card:
  family: diffraction_review
  mission: evaluate XRD-specific scientific inference
  semantic_status: proposal

variants:
  first_pass:
    objective: independent bounded assessment
  cross_exam:
    objective: test whether an answer closes XRD ambiguity

parameter_graph:
  nodes:
    - id: P:stress-vs-composition
      kind: mandatory_check
    - id: P:instrumental-reference
      kind: evidence_expectation
    - id: P:peak-assignment
      kind: competency
  edges:
    - [P:stress-vs-composition, REQUIRES, P:instrumental-reference]
    - [ROLE:xrd-specialist, CHECKS, P:peak-assignment]

compatibility:
  uncertainty_axes: [METHOD, NUMERIC_MEASUREMENT]
  methods: [METHOD_COMPATIBILITY, EXPERIMENTAL_RETEST]
  disciplines: [crystallography, materials_physics]

authority_refs:
  # References only. Runtime rights are resolved locally by policy.
  composition_policy_role_id: xrd_specialist
  grants_no_tools_or_evidence: true

provenance:
  source_cards: []
  benchmark_snapshots: []
  authoring_events: []
```

## Exchange rules

A PortableRoleDOM imported from another module/user is **never admitted automatically**.

Import pipeline should be:

```text
PortableRoleDOM
-> schema validation
-> semantic diff/equivalence analysis
-> authority stripping/check
-> compatibility checks
-> optional benchmark/review
-> RolePackAdmissionProposal
-> local policy owner/reducer
-> admitted local role version
```

The exchange format may carry `authority_refs` for mapping, but local tool/capability/evidence permissions must be recomputed from local policy.

## Relationship to RoleHandbookFillRequest

Current R4.3 code-generated handbook fill requests are a useful seed mechanism:

```text
runtime sees admitted role + missing semantic variant
-> RoleHandbookFillRequest
-> proposal-only skeleton
```

Future evolution:

```text
RoleHandbookFillRequest
-> RoleParameterGap[]
-> RoleGraphPatchProposal
-> candidate RoleVariantCard
-> round-trip role validation
-> versioned handbook/RoleCard update
```

This still must not become self-admitting policy mutation.

## Relationship to domain role packs

This design does not close TD-036. A domain role pack is an admitted/versioned packaging and policy problem; PortableRoleDOM is an interchange/semantic representation problem.

They may later connect as:

```text
PortableRoleDOM[]
-> DomainRolePack proposal
-> admission/conflict/equivalence validation
-> local policy mapping
```

## Future graph uses

A RoleParameterGraph could support:

- explainable role composition;
- comparison of near-synonymous specialists;
- identifying missing expertise parameters rather than inventing a whole persona;
- benchmark-driven role evolution;
- routing from AssessmentNeed to fine-grained role capabilities;
- role-reference fingerprinting and deduplication;
- organizational overlays without rewriting core role semantics;
- migration between Writer/Researcher/Coder review modules.

## Hard invariant

Portable role semantics may travel. **Authority does not travel with them.**
