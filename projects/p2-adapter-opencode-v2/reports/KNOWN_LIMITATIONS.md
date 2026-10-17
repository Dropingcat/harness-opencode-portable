# R1 known limitations (component-level)

Task r1-p2-adapter-20261017. This file is updated as gates complete; initial state =
worker slice verified at component level only.

## Confirmed by this R1 (component tests / static)

- Worker slice compiles (`py_compile` over the four modules) and was accepted by the
  factory contract validator (worker schema, written_by=worker).
- Modules are stdlib-only; no network/subprocess/credential surface in the new code
  (to be re-confirmed by the independent tester and reviewer gates).

## Not verified (deferred to R2 host canary)

- Trusted current-parent capability from an actual host invocation.
- Actual execution model vs requested model (host-reported metadata).
- Real parallel two-model isolation; real interrupt completion; late replies; real
  cleanup verification (`session.get` after delete).
- Real CLI subprocess deadline/cancellation behavior (R1 layer deliberately has no
  subprocess/network).
- Exact P2 schema/coverage against the live backend.

## Explicitly out of scope (blocked by contract)

- Host sessions/prompts/model backend; paid canary; real documents.
- Active canonical plugin/config/global agent changes; credentials.
- Any change that would weaken P2, coverage or DEGRADED policy.
- Dependency installation.

## Honest status wording

`R1_COMPONENT_VERIFIED / HOST_NOT_TESTED` is the ONLY claim this stage may make.
It is NOT P2_ROUTE_READY; TD-DEV-57..61 are not closed by this stage.