# Stage 2 — Attempt + GateSet + Evidence Events + State Reducer

Дата: 2026-09-06

## Что изменено

Второй этап убирает владение глобальным состоянием из reviewer/tester/auditor. Теперь агентские выходы не являются командами изменения state. Они проходят контрактную валидацию, превращаются в `AGENT_EVIDENCE` и попадают в append-only event log. Единственный компонент, который вычисляет состояние задачи, — `state_reducer.py`.

Каноническая цепочка:

`agent output -> contract_validator -> typed evidence event -> hash-chained event log -> State Reducer -> projection/state`

## Новые сущности

### Attempt

Каждый цикл исправления имеет отдельный `attempt_id` (`attempt-1`, `attempt-2`, ...). После `REQUEST_CHANGES` или `FAIL` текущая попытка закрывается как `REWORK`, а reducer/controller создаёт новую попытку с чистым GateSet. Старые провалы сохраняются как история, но не отравляют новую попытку.

`--limit N` теперь трактуется как максимальное число попыток, включая первоначальную.

### GateSet

Default policy: `config/factory_gate_policy.json`.

Обязательные gates:

- reviewer;
- tester;
- auditor.

Задача получает `PASSED` только если все обязательные gates текущей попытки находятся в `PASS`.

Reviewer APPROVE, tester PASS или auditor APPROVE по отдельности никогда не переводят задачу в PASSED.

### Typed evidence

`submit reviewer/tester/auditor/...` после contract validation создаёт evidence с:

- `evidence_id`;
- `agent_type`;
- `module`;
- исходным validated data;
- `attempt_id`;
- actor/event metadata.

Агент не передаёт `global_state`, `next_state` или иное управляющее поле.

### Event log

State format поднят до version 2. Источник состояния — `events[]`. `cycle`, `budget`, `attempts`, `evidence`, `verdicts`, `audit` являются materialized compatibility views и могут быть полностью восстановлены через replay.

Каждый event содержит:

- monotonically increasing `seq`;
- UUID `event_id`;
- `prev_hash`;
- SHA-256 `event_hash`.

При загрузке state hash-chain проверяется fail-closed. Ручная модификация старого события делает state недействительным.

### Frozen gate policy

При `TASK_CREATED` в event log сохраняются:

- полный snapshot gate-policy;
- `gate_policy_hash`.

Поэтому replay старой задачи не меняется после будущего редактирования `config/factory_gate_policy.json`.

## State transitions

Типичная успешная попытка:

`PENDING -> RUNNING -> reviewer PASS -> tester PASS -> auditor PASS -> PASSED -> DONE`

Rework:

`RUNNING -> gate RETRY -> REWORK -> ATTEMPT_STARTED(N+1) -> RUNNING`

Terminal reject:

`RUNNING -> gate FAIL -> FAILED`

Policy/manual block:

`RUNNING -> BLOCKED`

## CLI compatibility

Сохранены команды:

- `factory_ctl.py init`
- `factory_ctl.py submit`
- `factory_ctl.py budget`
- `factory_ctl.py auditor_block`
- `factory_ctl.py finalize`
- `factory_ctl.py status`

Добавлено:

- `factory_ctl.py replay`

`init` дополнительно поддерживает `--gates reviewer,tester,auditor` для явного GateSet. По умолчанию используется policy.

## Migration note

State version 1 намеренно не мутируется новым runtime. Старые state-файлы должны завершаться старой версией либо запуск должен быть переинициализирован. Автоматическая запись поверх v1 была бы опасной, поскольку семантика iteration/attempt и ownership состояния изменилась.

## Проверки

- `python -m unittest discover -s tests -v`: 12/12 PASS.
- `python -m compileall -q scripts mcp guard tests`: PASS.
- `python scripts/router/compile_runtime.py --check`: PASS.
- tamper test hash-chain: PASS.
- retry isolation test: PASS.
- all-required-gates test: PASS.
- attempt-limit test: PASS.

## Следующий архитектурный зазор

Следующий разумный этап — provenance уровня artifact/evidence: `artifact_id -> content_hash -> origin/tool -> guard verdict -> sanitized_ref -> evidence_id`. Текущий Stage 2 уже даёт место, куда этот provenance можно привязать без изменения ownership state.
