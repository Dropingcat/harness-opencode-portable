# TEST_STRATEGY.md: Стратегия тестирования v0.2

## 1. Уровни тестирования

| Level | Scope | Coverage Target | Tools | Owner |
| :--- | :--- | :--- | :--- | :--- |
| Unit | Functions, classes, pure logic | ≥ 90% logic | pytest, hypothesis | Developer |
| Integration | Component interaction, contracts | 100% critical paths | pytest, mocks | Developer |
| Security | Sandbox escape, injection, leaks | 100% threat model items | Custom scripts, bandit | Security/DevOps |
| E2E | Full cycle with real LLM | 5 golden tasks | run_local.py | QA/Tech Lead |
| Performance | Metrics eval, audit latency | < 10ms/100 iters | pytest-benchmark | Backend Dev |

## 2. Mandatory Test Scenarios

### 2.1. State Machine
-   All legal transitions succeed.
-   All illegal transitions raise `InvalidTransitionError`.
-   Property-based: random transition sequences never crash.

### 2.2. Anti-Hack/Lazy
-   Test file modification detected → BLOCK.
-   Cosmetic-only change detected → RETRY.
-   Oscillating findings detected → BLOCK.
-   Valid substantive change → PASS.

### 2.3. Sandbox Security
-   Fork bomb → killed within timeout.
-   Disk filler → blocked by RLIMIT/FSize.
-   Network access → connection refused/blocked.
-   Symlink escape → blocked.
-   Process spawn beyond limit → blocked.

### 2.4. LLM Gateway
-   Cache hit returns identical response.
-   Budget exceeded → error before API call.
-   Rate limit → exponential backoff retry.
-   Invalid JSON → retry with error context.

### 2.5. Auditor Separation
-   Auditor NEVER accesses artifact file content.
-   Auditor recommendations are process-only.
-   Critic NEVER reports process violations.

## 3. Fixtures & Mocks
-   **Golden Masters:** Fixed traces → fixed metrics (stored in `tests/fixtures/`).
-   **Synthetic Traces:** Generated for edge cases (stagnation, hacks, empty).
-   **Malicious Scripts:** Stored in `tests/security/fixtures/` for sandbox testing.
-   **Mock LLM:** Returns predefined responses based on input hash.

## 4. CI Requirements
-   All unit + integration tests pass.
-   Security tests pass.
-   MyPy strict mode passes.
-   Schema generation check (no drift).
-   Coverage report generated.
-   Secret scanning (no leaked keys).