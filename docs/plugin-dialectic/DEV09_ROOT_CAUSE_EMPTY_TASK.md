# DEV-09 — Root Cause: harness_run empty task (contract defect)

Дата: 2026-09-17
Статус: `ROOT_CAUSE_IDENTIFIED / FIX REQUIRED`

## Симптом (3/3 live-прогона, стабильно)

`harness_run` в live-сессии OpenCode возвращает:
- `state: ESCALATED`, `reason_codes: [REQUIRES_USER_OR_OPERATOR]`, `route_id: ""`
- для «проверить литературу по теме статьи» И «написать код парсера CSV».

Прямой вызов через `bridge_peer` / `resolve_route` даёт корректные маршруты
(`academic-research`, `code-implementation`). Расхождение — между live-плагином и прямым тестом.

## Корневая причина

1. `src/tools/harness_run.ts` объявляет `task` **необязательным**:
   `task: tool.schema.string().describe("Task text to route")` — БЕЗ `.required()`.
2. Модель вызывает tool без аргумента `task` (он не обязателен по схеме) → `args.task` = undefined.
3. `bridge.request("harness.run", { task: args.task, ... })` → в JSON поле `task` = undefined →
   на стороне peer `params.get("task") or ""` → `task = ""`.
4. `resolve("", hints={})` → `no_route_match` → `ESCALATED / REQUIRES_USER_OR_OPERATOR`.

Прямой тест всегда передавал `task` явно, поэтому не воспроизводил.

## Воспроизведение (детерминированно)

| task | resolve() | результат |
|---|---|---|
| `"проверить литературу..."` | `academic-research` | BUCKET_ASSIGNED |
| `""` | `None` | ESCALATED / REQUIRES_USER_OR_OPERATOR |
| `"  "` (пробелы) | `None` | ESCALATED / REQUIRES_USER_OR_OPERATOR |
| `None` | TypeError | (peer ловит как CORE_ERROR) |

Live-отчёт (ESCALATED, не TypeError) соответствует `task=""`.

## Исправление

`task` в `harness_run.ts` — сделать `.required()`:
```ts
task: tool.schema.string().describe("Task text to route").required(),
```
Плюс защита на стороне peer: если task пуст/пробелы — вернуть явную ошибку
`BAD_REQUEST: task required`, а не молчаливый no_route_match (чтобы не путать
«пользователь не передал задачу» и «роутер не нашёл маршрут»).

## Урок

- Первый отчёт (no_route_match 4/4) был **реальным дефектом live-пути**, а не артефактом
  самопровозглашения. Я ошибочно списал его на «пустой task от модели» без проверки
  обязательности поля. Скрупулёзная проверка (3 live-прогона + анализ контракта tool'а)
  выявила: дефект — в контракте `harness_run` (task не обязателен).
- `DEV09_VERIFICATION.md` и `DEV09_CALIBRATION_RESULT_1.md` требуют обновления
  после фикса: вывод «роутер работает» справедлив для прямого вызова, но live-путь
  был сломан контрактом tool'а.

## Действия

1. Исправить `harness_run.ts` (task.required()).
2. Добавить peer-защиту: пустой task → `BAD_REQUEST: task required`.
3. Пересобрать dist, переустановить плагин.
4. Пере-прогнать live E2E (тот же запрос) — ожидается `route_id` корректный.
5. Обновить DEV09_VERIFICATION.md / CALIBRATION_RESULT_1.md.