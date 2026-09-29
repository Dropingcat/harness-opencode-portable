# Переменные окружения Harness

**Дата:** 2026-09-22
**Принцип безопасности:** значения секретов НЕ хранятся в git и НЕ печатаются в документах. Только имена и назначение.

## Секреты

| Переменная | Назначение | Где хранится | Gitignored |
|---|---|---|---|
| `GITHUB_TOKEN` | Аутентификация GitHub (push в репозиторий harness) | `harness/.env` + `проект/.env` | ✅ (оба) |

## Использование

- В PowerShell: `$env:GITHUB_TOKEN`
- В bash: `$GITHUB_TOKEN`
- В Python: `os.environ['GITHUB_TOKEN']`
- При git push: `git -c credential.helper= push origin <branch>` (или настроить credential helper один раз).

## Не-секретные переменные

| Переменная | Назначение |
|---|---|
| `OPENCODE_HARNESS_ROOT` | Корень harness (`E:\Documents\Документы\doc_Opencode_agern-new`) |
| `RESEARCH_RUNNER_SH` | Путь к runner исследования |
| `RESEARCH_RULES_PATH` | Путь к правилам исследования |

## Правила

1. Секреты — только в `.env` (gitignored), никогда в `.md`/`.py`/коммитах.
2. При добавлении нового секрета — обновлять этот документ (имя + назначение).
3. Не логировать значения секретов (даже в trace).