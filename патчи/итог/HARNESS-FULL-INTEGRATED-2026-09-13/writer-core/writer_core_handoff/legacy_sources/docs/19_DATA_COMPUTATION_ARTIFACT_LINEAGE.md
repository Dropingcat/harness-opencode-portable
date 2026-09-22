# 19. Data, Computation & Artifact Lineage

## Computation graph

```text
RawData
→ CleaningStep
→ Transformation
→ Fit/Model
→ DerivedDataset
→ Quantity
→ Table/Figure
→ Claim
```

Each computation step records:
- executable/script hash;
- environment/package versions;
- parameters/random seeds;
- input hashes;
- output hashes;
- timestamp/run ID;
- validation status.

## Artifact-as-code

Figure/Table/Equation/CodeListing are typed artifacts, not opaque images/text.

Figure must bind:
- source dataset revision;
- generation script/parameters;
- axes quantities/units;
- series identities;
- caption claims;
- claims supported/illustrated.

Caption claims pass epistemic/RTT checks separately.

## Cross references

Document stores IDs (`FIG_06`, `EQ_11`), never hard-coded numbers. Renderer resolves numbering.

## Mutability

- RawData: IMMUTABLE
- Clean/DerivedData: DERIVED_REBUILDABLE
- Figure/Table: REBUILDABLE
- Approved external artifact: LOCKABLE

Silent editing of generated figures/tables without lineage creates `UNTRACKED_ARTIFACT_MUTATION` blocker.
