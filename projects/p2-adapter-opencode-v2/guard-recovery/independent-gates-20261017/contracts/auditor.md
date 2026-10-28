goal: Independently audit the PROCESS of the current local guard recovery and
its independent-check stage. This is not a code-quality review or a conflict
tribunal. Do not declare missing gates passed.

Dispatch envelope: if your current agent is code-auditor-runner, forward this
contract once to code-auditor using native V2 subagent(agent="code-auditor",
description="Guard process audit", prompt=<this contract>). In V2 this is the
wrapper's legacy task operation; agent replaces subagent_type. Inherit the
bound parent model; do not select a model. If your current agent is code-auditor,
assess only the metadata below yourself and do not delegate. No general agent
or primary self-audit. If the exact role is unavailable, stop with a transport
error. No nested agents or retries.

context:
- Process metadata only: %PROCESS_METADATA%
- The metadata contains authorizations, revision identities, role/dispatch
  observations, counters, and admission statuses. No worker code is supplied.
- Scope in: explicit recovery authorization, separation of author/reviewer/
  tester/process auditor, token/time limits, provenance and quarantined output,
  honest status of independent and host gates, absence of unauthorized merge.
- Scope out: source code, code paths, implementation correctness and style.
- Do not inspect the implementation, Git diff, candidate source or repository
  history. If information is insufficient, return REQUEST_CHANGES or
  INVALID_INPUT with the specific missing process fact.

output: Write %OUTPUT_JSON% as UTF-8 JSON (no BOM), then return a short status.
Schema: {verdict:"APPROVE|REJECT|REQUEST_CHANGES|INVALID_INPUT",
justification:string,process_analysis:{contracts_respected:boolean,
iteration_count:number,iteration_limit:number,role_violation:boolean,
reviewer_args_assessment:string,worker_args_assessment:string},requirements:[],
written_by:"code-auditor"}.

guard: Read only process metadata and the process document. No code, commands,
web, credentials, global configuration or Git mutations. Quarantined reviewer/
tester statements are not admitted evidence. Do not infer approval from process
exit codes or file existence. Your report also requires separate admission.
Budget: one concise process assessment, no retry loop.
