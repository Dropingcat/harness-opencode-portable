# 04. State-driven Routing

Routing inputs are entity state + blockers + policy + dependency readiness, not agent persona.

Precedence:
1. hard safety/policy/authority;
2. referential integrity;
3. source/data freshness;
4. epistemic eligibility/type compatibility;
5. blocking review/conflict;
6. structural completeness;
7. semantic realization/RTT;
8. optimization/style.

A route produces a typed operation. Executors are selected from CapabilityRegistry.

No route may automatically weaken a hard blocker into warning. No model result bypasses commit validators.
