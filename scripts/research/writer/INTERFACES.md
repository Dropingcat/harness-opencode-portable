# INTERFACES.md — Границы доменов verification / writer (У5)

## Цель

Разделить verification-домен (верификатор, claimeai-service) и writer-домен
(писатель, hermes resercher) как НЕЗАВИСИМЫЕ модули. Единственная связь между
доменами — файлы-артефакты (JSON), а НЕ python-импорты.

## Домены и пути

| Домен | Роль | Каталог |
|-------|------|---------|
| Verification (верификатор) | Проверка claims, числовые сравнения, вердикты | `/home/orangepi/projects/claimeai-service/scripts/` |
| Writer (писатель) | Планирование патчей, генерация текста, state machine | `/home/orangepi/.hermes/profiles/resercher/scripts/writer/` |

## Граница

**ПРАВИЛО:** writer НЕ импортирует verification-домен (claimeai,
verdict_schemas и т.п.), и verification НЕ импортирует writer. Кросс-импорты
запрещены. Связь — только через JSON-артефакты на диске.

## Контракты каналов

| Домен → Домен | Артефакт | Направление | Точка входа |
|---------------|----------|-------------|-------------|
| Verification → Writer | `verdicts_processed.json` | файл JSON | `patch_planner.plan_patches(verdicts_processed, ...)` |
| Writer → Verification | `verdicts_processed.json` (обновлённый) | файл JSON (re-verify) | `reverify.py` / повторная обработка |

## Формат артефакта `verdicts_processed.json`

Список объектов `list[dict]`. Ключи (не все обязательны):

| Ключ | Тип | Обязателен | Описание |
|------|-----|-----------|----------|
| `claim_id` | int | да | Идентификатор claim/группы |
| `claim_text` | str | да | Текст утверждения |
| `verdict` | str | нет | Один из `SUPPORTED`, `CONTRADICTED`, `UNSUPPORTED`, `AMBIGUOUS`, `OPEN` |
| `confidence` | float | нет | Уверенность в `[0, 1]` |
| `sources` | list | нет | Источники |
| `evidence` | list | нет | Доказательства |
| `caveats` | list | нет | Оговорки |
| `numeric_comparison` | dict | нет | Результат численного сравнения |
| `problematic` | bool | нет | Флаг проблемности |

## Правила интеграции

1. НИКАКИХ python-импортов между доменами. Только stdlib/локальные модули.
2. `writer/schemas.py` — локальные pydantic-схемы writer-домена (WriterStateModel). Не дублируют и не импортируют verifier-домен.
3. `verdict_schemas.py` (VerifierModel/VerdictModel) — живёт ТОЛЬКО в verification-домене.
4. Входная валидация в writer (`validate_verdicts_input`) — без импорта verifier-домена.
5. Поток данных: verification → `verdicts_processed.json` → writer `plan_patches` → `patch_plan.json` → writer → (re-verify) `verdicts_processed.json` (обновлённый) → verification.

## Проверка границ

`test_module_boundaries.py` (статический ast-анализ, без runtime) убеждается,
что в обоих доменах нет запрещённых кросс-импортов.