# DEV-09 Calibration — Verification of First Report

Дата: 2026-09-17
Статус: `REPORT_RECEIVED / ROUTER-CLAIM-NOT-REPRODUCED / CALIBRATION_PENDING`

## Контекст

Получен `dev09_live_calibration_report.json` (6 задач, T-01..T-06) и `process_errors_found.md`.
Главная находка отчёта: «маршрутизатор Core вернул `no_route_match` на 4/4 harness_run-запросах
(«проверить литературу по теме статьи», «написать код парсера CSV» и др.)».

## Детерминированная проверка (2026-09-17)

Проверено через три независимых пути:

| Путь | «проверить литературу» | «написать код парсера CSV» |
|---|---|---|
| `resolve_route.resolve()` (local) | `academic-research` / BUCKET_ASSIGNED | `code-implementation` / BUCKET_ASSIGNED |
| bridge_peer `harness.run` (local root) | `academic-research` | `code-implementation` |
| bridge_peer `harness.run` (portable) | `academic-research` | `code-implementation` |

Все три дают **корректную маршрутизацию**. Паттерны `runtime_snapshot.json` идентичны
в local / portable / deploy. TS-плагин (`harness_run.ts`) передаёт `task/route/profile` без искажений.

## Вывод (обновлено 2026-09-17 после root-cause)

ПЕРВОНАЧАЛЬНО вывод был «no_route_match не воспроизводится». Это было НЕВЕРНО:
дефект существовал, но в live-пути, а не в прямом вызове.

**Корневая причина найдена (см. `DEV09_ROOT_CAUSE_EMPTY_TASK.md`):**
- `harness_run.ts` объявлял `task` НЕобязательным (без `.min(1)`);
- модель вызывала tool без `task` → `args.task`=undefined → peer `params.get("task") or ""` → `""` → `resolve("")` → no_route_match;
- прямой тест всегда передавал task → не воспроизводил.

**Фикс (2026-09-17):**
- `task` → `.min(1)` (пустая строка отклоняется схемой);
- peer: пустой/пробельный task → явный `BAD_REQUEST: task required` (не no_route_match).

Воспроизведение до фикса: `resolve("")` → ESCALATED/REQUIRES_USER_OR_OPERATOR.
После фикса: `harness.run` с пустым task → CORE_ERROR/BAD_REQUEST; с валидным → маршрут.

Урок: скрупулёзная проверка требует проверить и live-контракт tool'а, а не только
прямой вызов Core. Три независимых live-прогона (3/3 ESCALATED) были верными.

## Что это значит для DEV-09

- Роутер-блокер из отчёта — **не подтверждён**; маршрутизация работает.
- Калибровка (grounding, MODEL_PRIOR leakage, advocate rationalization) — **в силе** как
  наблюдение поведения модели, но **не привязана к конкретным live harness_run вызовам**.
- Для валидной калибровки требуется повторный прогон с **детерминированной проверкой**:
  каждый harness_run-вызов подтверждается результатом bridge-вызова (route_id), а не
  пересказом модели.

## Действия

1. Зафиксировать этот документ в `docs/plugin-dialectic/DEV09_VERIFICATION.md` (local + portable).
2. Подготовить корректную процедуру повторного прогона (маршрут подтверждается кодом).
3. Остальные находки (MODEL_PRIOR leakage в T-01/T-05, T-02 норма, T-04 «64», T-06 variability)
   — валидные сигналы для калибровки, сохраняются.

## Fail-closed соблюдён в отчёте
- Core не редактировался, ответы не переписывались, mock не выдавался за live (отмечено в отчёте).
- Provider fallback не подменялся (активная пользовательская модель).