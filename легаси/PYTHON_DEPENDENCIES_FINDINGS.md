# Находки ревью Python-зависимостей (ДЛЯ АРХИВА / LEGACY)

Дата ревью: 2026-09-06.
Место полного нахождения: `../PYTHON_DEPENDENCIES.md` (в HARNESS).

## Ключевые находки для последующего изучения

1. **`mcp/doc_extract_server.py` — ЕДИНСТВЕННЫЙ модуль с внешними пакетами**
   (pypdfium2, python-docx, markdownify, openpyxl). Ленивые импорты.
   На системном venv hermes-agent эти пакеты ОТСУТСТВУЮТ → сервер зарегистрирован, но нерабочий.
   В legacy-копиях (doc_Opencode_agern_old, doc_Opencode_agern М2) этот файл идентичен.

2. **Ядро фабрики не требует внешних пакетов** — только stdlib Python 3.11.
   (scripts/code-factory, orchestration, memory, kanban, router, guard).

3. **PYTHONPATH загрязнён ChemOffice** (`...\ChemOffice2019\ChemScript\Lib`) — риск теневых модулей.

4. **`run_research.sh`** — Linux-only артефакт с hardcoded `/home/orangepi/...`;
   на Windows мёртв (трекинг-issue: `IMPLEMENTATION_TRACKER.md`).

5. **venv hermes-agent** содержит много легаси-пакетов (aiohttp, fastapi, google-api, edge-tts, openai),
   не нужных фабрике. Их чистить НЕ надо — это окружение самого hermes-agent.

## Состояние фикса (изоляция уже внедрена в HARNESS)
- Создан `.venv` (чистый, stdlib only) в HARNESS.
- `requirements-core.txt` (пуст) + `requirements-mcp-doc.txt` (опциональный doc_extract).
- `setup_env.ps1` переключён на `.venv`.
- `.gitignore` добавлен.
- 19/19 тестов проходят на чистом venv.

## Что осталось на ручное решение (в трекере HARNESS)
- Удалить ChemOffice из PYTHONPATH.
- Решить судьбу doc_extract: install в .venv или deactivate в mcp_lifecycle_config.
- run_research.sh — пометить явно Linux-only.