# Design checkpoint — hypothesis verification + OpenCode production semantic trace

Date: 2026-09-13
Canonical design commit: `7b42afe43c29397b51224b5f6876fe6f05044b47`
Parent runtime checkpoint: `11ec08550e81874fbd991449663849fd8f604315`

This checkpoint changes documentation/trackers only. Runtime code is unchanged.

Key additions:

- future `HypothesisCase / HypothesisRevision / VerificationPlan / HypothesisAssessment` architecture;
- hypothesis iteration through existing ResearchChallenge/ResearchDOM runtime;
- model-prior -> hypothesis proposal, never evidence;
- evidence independence/dependency problem (TD-049);
- source-bounded EvidenceDigest/HypothesisEvidenceLink direction (TD-050);
- 20-case virtual E2E suite before canonical implementation;
- production OpenCode semantic trace handoff contract;
- direct-local vs remote trace-pack execution modes;
- OpenCode artifact/reproducibility requirements without secrets.
