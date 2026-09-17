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

## Вывод

Утверждение отчёта «no_route_match на 4/4» **НЕ воспроизводится** ни в одном актуальном
Core. Вероятные причины:
1. live-прогон исполнялся в окружении со **старым** плагином/Core (до DEV-05/маршрутизации),
   либо `OPENCODE_HARNESS_ROOT` указывал на другой корень;
2. часть ролевых ответов — **самопровозглашённые** (модель описала ожидаемое поведение,
   а не реальные tool-вызовы) — согласуется с T-03 (self-modeled observer);
3. **`no_route_match` воспроизводится только на пустой `task`** (проверено: `resolve("", hints={})`
   → `ESCALATED / REQUIRES_USER_OR_OPERATOR`). Это указывает, что `harness_run` в live-прогоне
   получал **пустой/незаполненный task** — модель не передала текст задачи как аргумент,
   либо вызвала tool без аргументов.

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