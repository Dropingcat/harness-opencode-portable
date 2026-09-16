---
name: rivulet-numeric
description: Behavior-regression harness for the resercher pipeline numeric blocks (numeric_comparator, evidence_contract). Rivulet (ручейковые) micro-data cases: mode (a) block-in-isolation, mode (b) shared-input interaction. Deterministic checks only — no LLM judge. Fire on "run rivulet tests", "check numeric regression", "run nc evals".
compatibility: opencode 1.15.10+
version: 0.1.0
---

# rivulet-numeric

Ручейковые тесты для детерминированных модулей resercher:

- numeric_comparator.py (сравнение чисел claim vs source)
- evidence_contract.py (нормализация sources → evidence[])

Метод: микроданные → прогон одного блока (режим а) или общий вход
через два блока (режим б) → детерминированные проверки артефактов.

## Команды

```bash
# Baseline (зафиксировать текущее поведение как контракт)
eval-harness baseline --skill=rivulet-numeric

# Прогон всех кейсов
eval-harness run --skill=rivulet-numeric

# Один кейс
eval-harness run --skill=rivulet-numeric --case=nc-isolated-01
```

## Кейсы

| Кейс | Режим | Блок | Ожидание |
|---|---|---|---|
| nc-isolated-01 | (а) изоляция | numeric_comparator | match |
| nc-isolated-02 | (а) изоляция | numeric_comparator | mismatch |
| nc-isolated-03 | (а) изоляция | numeric_comparator | qualifier_mismatch |
| nc-interaction-01 | (б) общий вход | evidence_contract + numeric_comparator | согласованные evidence + comparison |