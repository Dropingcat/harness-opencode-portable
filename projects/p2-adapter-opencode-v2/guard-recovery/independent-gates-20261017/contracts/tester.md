goal: Independently reproduce the OFFLINE guard recovery checks at 892ecc3.

Dispatch envelope: if your current agent is code-tester-runner, forward this
contract once to code-tester using native V2 subagent(agent="code-tester",
description="Guard offline reproduction", prompt=<this contract>). In V2,
subagent is the wrapper's legacy task operation; agent replaces subagent_type.
Do not specify a model: inherit the bound parent model. If your current agent
is code-tester, run the scope below yourself, without further delegation.
No general agent or primary self-testing. If the exact role is unavailable,
report a transport error and stop. No nested agents or retries.

context:
- Candidate root: %CANDIDATE_ROOT%
- Scope in: existing guard suites and the two recovery regression files.
- Run exactly the authorized command below using the native V2 shell tool. It
  sets the owned harness/config/temp paths and runs the existing offline tests.
- Authorized command: %TEST_COMMAND%
- Do not execute newly generated tests before separate admission. If an
  additional case is needed, record its proposal as a problem, not executable
  code. No package installation, source fixes, provider calls or configuration
  edits. Do not read old reports, raw session dumps or other projects.
- Coverage is measured by the command, not estimated. The JSON coverage result
  and JUnit files are allowed outputs. Never reinterpret fixture PASS as a
  real-host result. If tooling is unavailable, report FAIL with the limitation.

output: Write %OUTPUT_JSON% as UTF-8 JSON (no BOM), then return a short status.
Schema: {module:"guard-recovery",result:"PASS|FAIL",passed:number,failed:number,
coverage:number,tests:[{name,result}],problems:[],written_by:"code-tester"}.
Use the actual command/JUnit/coverage results. No invented test outcomes.

guard: Only the exact offline test command and allowed output writes. No web,
real documents, credentials, git mutations or active plugin changes. Stop on
native permission denial instead of using an alternate command or transport.
The report remains quarantined; it cannot grant admission or integration.
Budget: one test invocation and one concise report, no retry loop.
