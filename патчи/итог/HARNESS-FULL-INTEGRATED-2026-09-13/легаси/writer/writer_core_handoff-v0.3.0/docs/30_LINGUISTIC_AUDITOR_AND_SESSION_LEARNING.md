# Linguistic Auditor and Session Learning

## Purpose
The Auditor learns language usage from completed work without turning every observed habit into a rule.

## Sources
Positive corpus:
- `HUMAN_ACCEPTED`;
- `EXPERT_ACCEPTED`;
- approved released text.

Negative/diagnostic corpus:
- `REJECTED`;
- `RTT_FAILED`;
- `HUMAN_REWRITTEN`;
- repaired model output.

Raw model output MUST NOT train preferences merely because it exists.

## Memory objects
The Auditor extracts:
- terminology and sense mappings;
- collocations;
- verb valency/government patterns;
- academic frames;
- connective usage;
- modality and causal expressions;
- metadiscourse patterns;
- paragraph/rhetorical patterns;
- author-specific sentence topology;
- recurring semantic failure patterns.

## LinguisticEpisode
Stores:
`context -> source_variant -> model_variant -> human/expert decision -> extracted features -> RTT outcome -> cost`.

## Promotion lifecycle
`OBSERVED -> CANDIDATE -> SHADOW -> EVALUATED -> PROMOTED | REJECTED`.

Only promoted patterns influence normal ranking. Promotion affects `LEARNED_PREFERENCE`, not epistemic truth.

## Style trajectory
Author profile is time- and genre-conditioned. The system stores revisions/distributions rather than one eternal centroid. Old observations MAY decay. Journal/template-induced language MUST be separated from author preference.

## Anti-poisoning
The Auditor MUST track provenance of every learned feature and MUST support rollback of preference revisions.
