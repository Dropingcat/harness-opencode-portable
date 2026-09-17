# Pipeline Run Status — Writer / Researcher / Coder

Дата: 2026-09-17
Статус: `READY FOR SCENARIO RUNS`

## Инструмент harness_run в текущей среде

- **С явным `route`**: работает корректно (полный маршрут: capsules, skills, tools, bindings).
- **Без `route` (авто-детект)**: стабильно `ESCALATED / no_route_match` для непустых задач,
  хотя bridge_peer (тот же код, тот же snapshot, policy_hash `8910fd…`) даёт корректные
  маршруты (`academic-research`, `code-implementation`).
- Вывод: инструмент подключён к peer-процессу, отличному от bridge_peer, который
  тестируется напрямую (вероятно, поднят ранее/другой транспорт/кэш). policy_hash совпадает,
  поэтому snapshot тот же; расхождение — в исполняемом коде/окружении peer.
- Не блокирует прогоны: сценарии выполняются с явным `route` (детерминированно).

## Сценарии (пайплайны)

### 1. Researcher — `academic-research` (strict)
- Маршрут подтверждён: 2 capsules, 12 skills, 5 tools, guard untrusted.
- Цепочка: маршрут → capsules → arxiv/openalex → claims → верификация.
- Покрывает TD-009, TD-017, TD-038; DEV-09 (live).

### 2. Writer — `writing-prose`
- Цепочка: draft → RTT → citation trace → DOM.
- Покрывает DEV-02, DEV-08.

### 3. Coder — `code-implementation`
- Цепочка: worker → reviewer → tester → auditor (через semantic transport).
- Покрывает TD-062, DEV-05.

## Диагностический долг (отдельно)
- `harness_run` без route в live-среде: peer mismatch — требует проверки, какой именно
  peer-процесс обслуживает инструмент (кэш MCP/плагина). Записан как follow-up.

## Результаты
- (заполняется по мере прогонов: JSON по протоколу DEV-09)