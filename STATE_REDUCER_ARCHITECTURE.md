# State Reducer Architecture

## Инвариант

Ни worker, ни reviewer, ни tester, ни auditor не являются владельцами task state.

Они производят только данные. Все переходы вычисляются deterministic reducer из immutable event history и frozen policy snapshot.

## Runtime boundaries

1. `contract_validator.py` проверяет shape и обязательные поля agent output.
2. `factory_ctl.py` является command facade. Он не содержит бизнес-логики переходов.
3. `code_factory_runner.py` владеет append-only event log, atomic persistence, retry event emission и replay facade.
4. `state_reducer.py` является единственным местом, где agent evidence интерпретируется как gate outcome и task projection.
5. `factory_gate_policy.json` задаёт gate semantics для новых runs. Его snapshot фиксируется внутри `TASK_CREATED`.

## Основные инварианты reducer

- PASS возможен только при PASS всех required gates текущего attempt.
- Evidence предыдущего attempt не участвует в GateSet нового attempt.
- Retry не стирает историю.
- Terminal FAIL/BLOCK нельзя исправить новым agent evidence без отдельного explicit recovery protocol.
- DONE возможен только из PASSED.
- Budget block вычисляется reducer, а не агентом.
- Replay одинаковой event history должен давать одинаковую projection.
- Event history проверяется hash-chain до использования.

## Почему projection хранится рядом с events

Projection сохранена в JSON ради совместимости существующих readers и удобства диагностики, но она не authoritative. При каждом load/save она пересчитывается из events. Поэтому её ручное изменение не имеет смысла и не должно использоваться как API записи.
