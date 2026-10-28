# PLAN: Реализация TD-174..177 через фабрику (параллельные ветки git)

Дата: 2026-10-02
Оркестратор: code-orchestrator (эта сессия)
Контур: coder → code-factory

## Контекст (ревью)

- **TD-174** (аудит суб-агентов): нет live-мониторинга. Есть `agent_loop.py` (TD-173, итеративный resume) — фундамент.
- **TD-175** (разделение памяти): `memory_l1/l2/l3_policy.json` + `memory_registry.json` есть, но нет per-agent namespace, session tracker, light-memory. `memory_bridge.py` отсутствует в portable (есть в live-конфиге).
- **TD-176** (авто-подсказки роутера): `resolve_route.py` возвращает route/agent/tools, но нет task_class/hint/dashboard.
- **TD-177** (skill оценки задачи/контекста): контракт глубины (TD-170) есть в `shared/search-depth-contract.md`, но нет шаблона роутера/skill.

**Блокер инфраструктуры:** meta-слой (аудитор v2, damage basket, sleep controller, health monitor, memory circulator) существует ТОЛЬКО в work-дереве (`E:\Documents\Документы\doc_Opencode_agern-new\scripts\meta\`), в portable отсутствует. Внешний CLI opencode недоступен (harness-deploy удалён, TD-173) — поэтому фабрика запускается через task-субагентов (coder-worker/code-reviewer/code-tester/code-auditor), что эквивалентно внутреннему контуру.

## Ветки git (от текущей HEAD feature/improve-mcp-resolver)

| Ветка | Модуль | Что делает |
|---|---|---|
| `feature/td174-supervisor` | M1 | `scripts/tools/agent_supervisor.py` — live-аудит суб-агентов (heartbeat, детекция отклонений, авто-перезапуск, лимит, L2-запись) |
| `feature/td175-memory-router` | M2 | `scripts/memory/memory_bridge.py` + memory_namespace (per-agent/shared) + session_tracker.json + light-memory при switch |
| `feature/td176-router-hints` | M3 | `resolve_route.py` → task_class + task_hint + dashboard (HP/damage/active TD) из meta-слоя |
| `feature/td177-context-skill` | M4 | шаблон `task_context_assessment` в tool_skill_templates.json + skill `task-context-assessment` |
| `feature/meta-portable` | M0 | перенос `scripts/meta/*` (auditor_v2, damage_basket, sleep_controller/planner, health_monitor, memory_circulator) из work в portable + запуск демона аудитора |

## Порядок

1. **M0** (инфраструктура, параллельно с остальными): перенос meta-слоя → portable, запуск демона с контрактом.
2. **M1..M4** — параллельно (независимые ветки).
3. Интеграция: merge M0 → M4 в `feature/improve-mcp-resolver` в порядке M0, M4, M1, M2, M3 (по зависимостям).
4. Тесты полного цикла: unit-тесты каждого модуля + smoke-тест демона аудитора (basket+damage+sleep contract) + проверка resolve-подсказки.

## Acceptance (общий)

- Каждый модуль: py_compile + unit test (pytest) PASS.
- M0: `meta_daemon.py --once` даёт аудит артефакта → damage → sleep contract (файл `.meta_state/<orch>_sleep_contract.json`).
- M1: на зациклившемся субагенте supervisor детектирует и перезапускает (лимит 2).
- M2: `switch research-orchestrator → source-fetcher` подтягивает только global + namespace + light-memory.
- M3: `resolve --task "найти источники"` → task_class=search + hint + dashboard.
- M4: шаблон task_context_assessment выдаёт depth/stop_criterion.