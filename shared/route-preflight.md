# Route Preflight (M1 / E2E-02)
**Назначение:** детерминированная проверка маршрута на старте сессии оркестратора.

## Порядок (шаг «route preflight» в ритуале старта)
1. `harness_status` (или `mcp__coder_router__coder_run`) → проверить доступность роутера.
2. Определить route по типу задачи (code-implementation / web-research / writing-prose / ...).
3. Записать в PROGRESS: `ROUTE=<route>` + `BUNDLE=<bundle>`.

## Критерий PASS
- Тула роутера доступна (не «unknown tool»).
- ROUTE определён и записан.
- При недоступности роутера — STOP с `CWD_ERROR` (не продолжать вслепую).

## Привязка
- Матрёшка Слой 1 (M1): чек `ROUTE` в PROGRESS.
- Кодеры: code-orchestrator (ритуал старта), writing-orchestrator, research-orchestrator.