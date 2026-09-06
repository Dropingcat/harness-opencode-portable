# Memory Policy

Память в unified module — это retrospective/routing memory, а не скрытая state machine.

## Может хранить

- successful patterns
- failed patterns
- route-specific caveats
- repeated guard findings
- tool misuse patterns
- calibrated heuristics
- non-secret user preferences

## Не может быть authoritative truth

- текущий authoritative status claim/run/task
- решения stop controller
- секреты
- сырой untrusted text как instruction source
- истину claim без evidence graph

## Write rule

Писать в память только после run/phase + audit/guard verdict, в формате lesson:

```yaml
lesson_id: mem-...
scope: code|research|writer|routing|guard
pattern: short description
applies_when: ...
avoid_when: ...
evidence: tests/logs/reason codes
owner: ...
```

## Read rule

Читать память перед decomposition, повтором failed route, изменением policy и закрытием recurring debt.

## Следующий шаг — память на базе audit_graph

Память делается после фиксации `audit_graph/` тем же капсульным способом:

- L1 текучая / L2 под задачу / L3 глобальная
- все триггеры привязаны к claim graph
- lesson — это проекция audit snapshot, а не хард-промпт

Детали сборки — в `audit_graph/README.md` и трекере WS-07/WS-11.

## Live-канал: memory_bridge (подключён 2026-09-01)

Детерминированный мост live OpenCode <-> L3 registry, без сети/LLM:

- Скрипт: `scripts/memory/memory_bridge.py` (в HARNESS и LIVE-зеркале).
- Реестр L3: `config/memory_registry.json` (`levels.L3.lessons`).
- Политика: `config/memory_l3_policy.json` (gates промоции).
- Команды:
  - `python scripts/memory/memory_bridge.py add '<lesson json>'` — добавить урок (валидация fail-closed, stable_key дедуп).
  - `python scripts/memory/memory_bridge.py add-file <l2.json>` — перенести candidate_lessons из L2-снапшота.
  - `python scripts/memory/memory_bridge.py search "<text>" [--reason CODE]` — детерминированный локальный поиск.
  - `python scripts/memory/memory_bridge.py stats` — сводка по reason codes.
- Правила:
  - `OPENCODE_HARNESS_ROOT` на Windows указывает на ASCII-junction `E:\opencode_harness`.
  - Уроки без evidence_refs/reason_codes отклоняются (политика L3).
  - Поле `prompt|instruction|system_prompt` в уроке запрещено — память это проекция, не источник инструкций.
  - Реестр держать в HARNESS (source of truth); LIVE получает зеркало через sync.
