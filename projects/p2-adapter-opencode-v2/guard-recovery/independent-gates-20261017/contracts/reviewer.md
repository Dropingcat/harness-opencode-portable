goal: Independently review guard-recovery checkpoint 892ecc3. This is local
recovery review, not production admission or a P2 host test.

Dispatch envelope: if your current agent is code-reviewer-runner, forward this
contract once to the registered code-reviewer. In installed OpenCode V2 2.0.29,
the wrapper's legacy task operation is named subagent, and subagent_type is
named agent: use subagent(agent="code-reviewer", description="Guard recovery review",
prompt=<this contract>). This is the same exact role, not an alternate transport
or a fallback. Do not specify a model; the bound parent model is inherited.
If your current agent is code-reviewer, execute the scope below yourself and
do not delegate. No general agent, primary self-review, nested delegation or
retries. If the exact role is unavailable, return a transport error and stop.

context:
- Candidate root: %CANDIDATE_ROOT%
- Read ONLY these source/test files, the diff and the local process document:
  guard/src/semantic_layer.py (configured_provider_names, ClassifierChain._build),
  guard/src/artifact_guard.py (deadline, preflight, scan_artifact),
  guard/src/opencode_transport.py (ClassificationReply and DTO context),
  guard/src/native_semantic_transport.py,
  scripts/tools/doc_guard.py,
  tests/coder/test_guard_recovery.py,
  tests/coder/test_native_classifier_recovery.py.
- Last diff: %DIFF_FILE%
- Scope in: disabled/unavailable routes cause no connection; no implicit local
  route; caller deadline cannot expand config bound; no route fails promptly;
  native explicit YES/NO, correlation, duplicate-message rejection; unchanged
  P2/coverage/hash criteria and clearly disconnected real-host integration.
- Scope out: actual OpenCode host wiring, other branches, general repository
  cleanup, styling, legacy unrelated functions, process acceptance.
- No previous reviewer verdict is supplied. Form an independent judgement.

output: Write %OUTPUT_JSON% as UTF-8 JSON (no BOM), then return a short status.
Schema: {module:"guard-recovery",verdict:"APPROVE|REQUEST_CHANGES|REJECT",
comments:[{file,line,problem,suggestion,falsification}],
scope_declared:{scope_in:[],scope_out:[]},out_of_scope_gaps:[],written_by:"code-reviewer"}.
Prioritize concrete safety/correctness defects. Each comment must cite the
relevant changed file/line and an observation that would falsify it. Do not
invent defects or hide out-of-scope gaps in blocking comments.

guard: No web, session history, external documents, credentials, active config
or provider calls. Do not run commands or modify candidate code. Native
permissions may deny an action: report the exact limitation, never bypass it.
Your output remains quarantined until the separate guard admission step.
Budget: one review pass, concise JSON and final status; no follow-up loops.
