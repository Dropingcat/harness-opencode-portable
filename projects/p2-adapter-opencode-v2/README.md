# PROJECT: p2-adapter-opencode-v2

**Дата создания:** 2026-10-17
**Владелец:** code-orchestrator
**PROJECT_ID:** p2-adapter-opencode-v2
**Статус:** ACTIVE — R1_IN_PROGRESS (component recovery), P2-маршрут НЕ готов, host НЕ проверен.

## Цель

Реализовать P2-adapter через штатный OpenCode 2.0.29 transport (native semantic transport),
использующий provider/model конкретной родительской сессии, credentials внутри OpenCode,
с сохранением P2-схемы, покрытия и fail-closed. Без скрытого fallback на Polza/local.

## Связанные долги

- TD-R1-P2-ADAPTER-01 (HIGH, OPEN) — R1 component implementation.
- TD-CONTRACT-DISPATCH-01 (HIGH, OPEN) — конкурентная задача (генерация контрактов), не входит в scope.
- TD-DEV-57..61 — блокеры диспатча ролей фабрики (контекст, НЕ scope R1).

## Структура

```text
projects/p2-adapter-opencode-v2/
├── artifacts/           # MANIFEST.json, factory_state.json, evidence/ (git-версионируется)
├── runs/                # рантайм (НЕ в git)
├── reports/             # R1 docs: BASELINE, ARCHITECTURE_DELTA, CHANGES, KNOWN_LIMITATIONS, NEXT_STAGE, R2_HOST_CANARY_PLAN
├── tech_debt.md         # TD-реестр проекта
├── README.md
└── config.env           # переменные проекта
```

## Правила

- Артефакты звеньев — в `artifacts/` (git), рантайм — в `runs/` (не в git).
- `tmp/` и `temp/` — ТОЛЬКО временное хранение: черновики/осколки текущей сессии, **стираются по итогу сессии** (канон: `12_PROJECT_ARTIFACTS.md` §3.1). Постоянные артефакты — только здесь, в `projects/p2-adapter-opencode-v2/`.
- Реализация живёт в изолированном worktree `C:/Temp/opencode/r1-p2-adapter` (ветка `r1/p2-adapter-20261017`);
  активная canonical-сборка не изменяется (manifest: worker_commit 19afcfb).
- Протестировано/реализовано/host-проверено разделяются строго.

## Текущая точка

- Worker: PASSED. Tester/Reviewer/Auditor: PENDING. host_calls=0, model_calls=0.
- Следующий шаг: независимые gates (tester/reviewer/process auditor), затем R2 host-canary (отдельный допуск).