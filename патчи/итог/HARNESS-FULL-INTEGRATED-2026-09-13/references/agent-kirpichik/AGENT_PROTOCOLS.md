# AGENT_PROTOCOLS.md: Протоколы взаимодействия агентов v0.2

## 1. Sequence Diagram

```
Orchestrator          Coder           Verifier        Critic          Auditor
     |                  |                |              |               |
     |--generate(spec)->|                |              |               |
     |<--artifact-------|                |              |               |
     |--verify(art)---->|                |              |               |
     |                  |--run(sandbox)->|              |               |
     |                  |<--results------|              |               |
     |<--tool_results---|                |              |               |
     |--evaluate(art,tr)|                |              |               |
     |<--CriticReport-------------------|              |               |
     |                  |                |              |               |
     |[Policy Check]    |                |              |               |
     |                  |                |              |               |
     |[Should Audit?]---------------------------------->|               |
     |<--AuditReport-------------------------------------|               |
     |                  |                |              |               |
     |[Update Kanban]   |                |              |               |
     |[Next Iteration / Stop]            |              |               |
```

## 2. Контракты вызовов

### 2.1. Coder
-   **Input:** `(spec: str, context: TaskContext, fix_notes: List[FixNote])`
-   **Output:** `Artifact`
-   **Guarantees:** Stateless, deterministic (for stubs), no side effects.
-   **Error Handling:** При ошибке возвращает исключение `CoderError`, оркестратор эскалирует.

### 2.2. Critic
-   **Input:** `(artifact: Artifact, tool_results: Dict)`
-   **Output:** `CriticReport`
-   **Guarantees:** Cold (no history), stateless, no code modification suggestions.
-   **Error Handling:** При ошибке парсинга LLM → retry с error context → эскалация после N попыток.

### 2.3. Auditor
-   **Input:** `(trace: List[TraceEntry], metrics: ProcessMetrics, config: Dict)`
-   **Output:** `AuditReport`
-   **Guarantees:** Never reads artifact content, only metadata/hashes/metrics.
-   **Error Handling:** Fail-open для warnings, fail-closed только для явных BLOCK-паттернов.

### 2.4. Orchestrator
-   **Input:** `(spec: str, context: TaskContext)`
-   **Output:** `TaskResult(status, artifact, trace, metrics_history)`
-   **Guarantees:** Deterministic state transitions, local trace (no global state), safe cleanup on error.
-   **Stop Criteria:** verdict=PASS, requires_user=True, iteration_limit, auditor_block.

### 2.5. Verifier
-   **Input:** `(artifact: Artifact, tools: List[str], sandbox: SandboxRunner)`
-   **Output:** `Dict[str, ToolResult]`
-   **Guarantees:** Runs inside sandbox, never on host. Raw output preserved on parse error.
-   **Error Handling:** Parse errors return raw output, never raise. Sandbox escape → kill + block.

## 3. Error Propagation Matrix

| Agent | Error Type | Action | Escalate? |
| :--- | :--- | :--- | :--- |
| Coder | Invalid output schema | Retry (max 2) → Block | Yes |
| Coder | Timeout | Block immediately | Yes |
| Critic | Invalid JSON | Retry with error ctx → Block | Yes |
| Critic | Ambiguous verdict | Set requires_user=True | Yes |
| Auditor | Pattern detector error | Log warning, continue | No |
| Auditor | Block violation | Set block=True | Yes |
| Verifier | Sandbox escape attempt | Kill sandbox, Block | Yes |
| Verifier | Tool parse error | Return raw output, continue | No |
| LLM | Rate limit (429) | Exponential backoff retry | No |
| LLM | Budget exceeded | Block immediately | Yes |

## 4. State Machine Transitions

```
PENDING → RUNNING → PASSED (verdict=PASS)
                  → FAILED (verdict=FAIL, iteration_limit)
                  → AMBIGUOUS (requires_user=True)
                  → BLOCKED (auditor_block)
```

| From | To | Trigger |
| :--- | :--- | :--- |
| PENDING | RUNNING | Orchestrator starts cycle |
| RUNNING | PASSED | Critic verdict=PASS |
| RUNNING | FAILED | Critic verdict=FAIL + iteration_limit |
| RUNNING | AMBIGUOUS | Critic requires_user=True |
| RUNNING | BLOCKED | Auditor block=True |
| AMBIGUOUS | RUNNING | User response received |
| BLOCKED | PENDING | Config/task adjusted, re-run |