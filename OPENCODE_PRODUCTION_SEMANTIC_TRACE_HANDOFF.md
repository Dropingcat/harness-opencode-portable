# OpenCode production semantic trace — handoff and reproducibility contract

Date: 2026-09-13
Status: operational integration note for R4.4 L3B production semantic gate.

## 1. Purpose

R4.4 L3A/L3B already proves the control path structurally:

```text
DDC / DQC / ADC
→ RoleProviderBinding (RPB)
→ TribunalExecutionEnvelope (TEX)
→ logical tool / runtime binding
→ Job / Attempt
→ ProviderExecutionReceipt (PER)
→ IQT / ARG
→ ArgumentGraph admission
→ DialecticObserver
```

The remaining gate is not another contract. It is a trace from an actual semantic OpenCode worker using these unchanged contracts.

## 2. Current execution environment

Current sandbox/runtime observed on 2026-09-13:

```text
OS: Linux
architecture: x86_64
libc: glibc 2.41
Python: 3.13.5
Node: 22.16.0
Bun: not installed
Ollama: not installed
OpenCode: not installed
external DNS/network from container: unavailable
```

Therefore a standalone OpenCode executable can be exercised here at the CLI/process layer, but a cloud semantic model cannot be reached from this sandbox unless the environment changes.

## 3. Exact CLI contract already used by the Harness

The current launcher calls:

```text
opencode run --pure \
  --model <MODEL> \
  --dir <RUN_DIR> \
  <FULL_CONTRACT_PROMPT>
```

The executable path may be overridden with:

```text
OPENCODE_BIN=/path/to/opencode
```

The worker is expected to write:

```text
<RUN_DIR>/results.json
```

The Harness also records launcher `meta.json`, `result.json`, stdout/stderr and later a durable `PER-*`.

## 4. Preferred OpenCode package to provide

### Best option for execution in this sandbox

Provide a **portable Linux x86_64 OpenCode build/distribution** matching the version intended for production.

Preferred contents:

```text
opencode
VERSION.txt or `opencode --version` output
optional LICENSE/NOTICE
any adjacent runtime/assets required by that exact build
sanitized config example
```

The ideal artifact is a self-contained executable or official portable archive. Avoid an installer that requires root/package-manager mutation.

### If OpenCode requires Bun

Bun is not installed here. Either:

- provide a standalone OpenCode binary that does not require a system Bun; or
- provide the complete portable OpenCode + Bun runtime bundle with the exact launcher command.

### If only source is available

A source archive is useful for compatibility review but is weaker for production trace because it introduces a new build step/version boundary. Prefer the exact built artifact used on the target server.

## 5. If the production server uses ARM64

For a production server running ARM64, the strongest reproducibility package is **two builds of the same OpenCode version**:

```text
linux-arm64
  exact artifact actually deployed on the server

linux-x86_64
  same OpenCode version/build line for execution in this sandbox
```

The ARM64 artifact lets the Harness record the real deployment fingerprint; the x86_64 artifact lets this environment exercise the CLI/runtime path.

Do not assume binary identity across architectures. Record version/build/source revision for both.

## 6. Model/provider configuration to include

The current launcher default is:

```text
ollama-cloud/glm-5.2
```

but the production trace does not depend on that exact model. Provide the model/provider combination actually intended for use.

Useful non-secret information:

```text
model identifier
provider type
OpenCode config file with secrets removed
names of required environment variables
endpoint type / local-vs-cloud
context/output limits if configured
```

Do **not** send API keys, bearer tokens or account secrets in the archive/chat.

## 7. Network limitation and two trace modes

### Mode A — direct local semantic trace

Possible only if the supplied environment includes a model/provider reachable without external network, for example a local/offline endpoint available inside the execution environment.

This gives the strongest direct E2E here.

### Mode B — remote production trace pack (recommended for cloud OpenCode)

Because this sandbox has no external DNS, the practical production path is:

```text
Harness here
→ compile exact DDC/DQC/ADC/RPB/TEX trace pack
→ user runs pack on production server with real OpenCode/model credentials
→ user returns run artifacts
→ Harness validates/adopts result through unchanged PER/IQT/ARG admission
```

Secrets remain on the production server.

## 8. Future trace-pack format

Candidate package:

```text
opencode_trace_pack/
  TRACE_MANIFEST.json
  execution_envelope.json
  contract.md
  expected_output_schema.json
  provider_binding_snapshot.json
  role_instruction_snapshot.json
  disclosure_contract.json
  question_or_defense_contract.json
  run_trace.sh
  SHA256SUMS
```

`TRACE_MANIFEST.json` should record:

```text
trace_pack_version
RPB id/fingerprint
TEX id/fingerprint
DDC/DQC/ADC ids/fingerprints
role/variant
branch key
expected OpenCode version/build
model identifier
expected output schema
input file hashes
```

## 9. Returned production trace

Return only non-secret artifacts such as:

```text
opencode --version output
actual model identifier
run_dir/meta.json
run_dir/result.json
run_dir/results.json
captured stdout/stderr
execution timestamps/duration
OpenCode binary SHA256
sanitized config hash
trace-pack SHA256
```

Do not return secret environment values.

The Harness can then reconstruct:

```text
DQC/ADC
→ RPB
→ TEX
→ external production execution
→ raw semantic result
→ PER
→ deterministic validation
→ IQT/ARG admission or rejection
```

## 10. Production semantic acceptance cases

Do not test only a happy answer. The first production campaign should include:

1. evidence-grounded specialist answer;
2. useful MODEL_PRIOR hypothesis with no source;
3. hallucinated evidence ref;
4. attempt to use hidden sibling evidence;
5. answer evasion;
6. false Q2 novelty / paraphrase-only continuation;
7. correct CONCEDE_LOCAL_POINT;
8. Advocate evidence-grounded QUALIFY/DEFEND;
9. Advocate rhetorical MODEL_PRIOR defense that must become REQUEST_EVIDENCE;
10. insufficient evidence -> OPEN;
11. one question addressed to wrong specialist as negative binding control;
12. multidisciplinary second role family with different evidence/method view.

## 11. Reproducibility requirements

For every production semantic trace preserve:

```text
OpenCode version/build/hash
model identifier
provider/config hash (sanitized)
RPB/TEX/DDC/DQC/ADC fingerprints
role instruction fingerprint
policy hashes
branch/history fingerprint
raw provider output hash
PER id/fingerprint
admitted IQT/ARG ids or rejection reason
```

This is the minimum useful provenance if later OpenCode/model versions produce different scientific behavior.

## 12. What to send now

Preferred immediate upload:

```text
1. Linux x86_64 portable OpenCode executable/archive
2. `opencode --version` or build/version metadata
3. sanitized OpenCode config used for the intended model/provider
4. short README with the exact command you normally use successfully
```

If your actual server build is ARM64, include that production artifact too if convenient, but the x86_64 build is required for direct execution in this sandbox.

If cloud access is mandatory, the x86_64 binary is still useful for CLI/integration verification; the actual semantic trace should then use the remote trace-pack workflow.

## Concrete user-supplied build received

The uploaded Windows installer identifies itself as OpenCode **1.18.30** (`FileVersion` and `ProductVersion`). Installer SHA256:

`dcf723272c930f5dfa73a8561818ae4ad1a346384a859111ffeb554e19ce6567`

For the server acceptance, use a native server CLI of the same version/build line where possible. The remote report records the actual server executable path/version/SHA256, so a different server build remains auditable rather than being silently treated as identical.

## Automated remote acceptance entrypoint

The deployment checkpoint contains:

```bash
python scripts/remote_acceptance/run_remote_acceptance.py \
  --model '<EXACT_PRODUCTION_MODEL_ID>' \
  --opencode-bin opencode \
  --timeout 180 \
  --output remote_acceptance_runs/production_001 \
  --archive
```

The worker uses the same bounded provider contract, RPB/TEX/PER path and deterministic admission as the Harness runtime. API credentials stay on the production host.
