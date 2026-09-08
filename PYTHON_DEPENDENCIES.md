# Ревью Python-зависимостей: изоляция и мусор (2026-09-06)

## Вывод
Ядро фабрики кода **не требует ни одного внешнего Python-пакета**. Все подсистемы
(scripts/code-factory, orchestration, memory, kanban, router, guard) используют
**только стандартную библиотеку Python 3.11**. Изоляция достижима чистым venv
без установки чего-либо.

## Что проверили (факты, не выводы)

### 1. Потребители внешних пакетов
| Компонент | Импорты | Внешние пакеты? |
|---|---|---|
| scripts/code-factory/* (reducer, runner, ctl, validator, provenance) | — | ❌ stdlib only |
| scripts/orchestration/* (character_sheet, idle_tasks, delegation_score) | — | ❌ stdlib only |
| scripts/memory/* (bridge, collect_l2, promote_l2_to_l3) | — | ❌ stdlib only |
| scripts/kanban/* | — | ❌ stdlib only |
| scripts/router/* | — | ❌ stdlib only |
| guard/src/* | — | ❌ stdlib only |
| **mcp/doc_extract_server.py** | `pypdfium2`, `docx`, `markdownify`, `openpyxl` | ✅ **ПН СТОЛЬКО** |

>>> **Единственный модуль с внешними пакетами — `mcp/doc_extract_server.py`** (PDF/DOCX/HTML/XLSX → markdown).
    Импорты ленивые (внутри функций), поэтому отсутствие пакетов не ломает старт фабрики.

> **Важно (2026-09-08):** OCR-капсула capability-оверлея (`scripts/capsules/`, `document.ocr`)
> требует **внешний бинарник Tesseract** (`C:\Program Files\Tesseract-OCR`, v5.4.0, установлен),
> а НЕ Python-пакет. В `requirements-capability-bundle.txt` он намеренно отсутствует; проба —
> `shutil.which('tesseract')` (executable probe). Установка/обновление — системный инсталлер
> UB-Mannheim, не pip. Языки: `eng`, `osd`, `rus`, `equ` (tessdata_fast). Детали:
> `DEPENDENCY_MATRIX.md`.

> **Важно (2026-09-08):** `web.discovery` требует **SearXNG-сервис** (HTTP API на
> `127.0.0.1:8888`). Поднят нативно (без Docker) в `E:\Documents\searxng\` (свой venv,
> git-клон searxng, Windows-патч для `import pwd`). Это сервис, а не pip-зависимость;
> preflight проверяет его liveness HTTP-запросом. Автозапуск — Windows Task «SearXNG».
> Детали: `DEPENDENCY_MATRIX.md`.

### 2. Состояние venv (системный, hermes-agent)
- `sys.executable` = `...\hermes-agent\venv\Scripts\python.exe` (Python 3.11.15)
- В site-packages — большой мусор от hermes-agent и легаси: aiohttp, fastapi, google-api, edge-tts, openai, etc.
- **Отсутствуют** docx/markdownify/pypdfium2/openpyxl (doc_extract НЕ работает на этом venv).

### 3. Загрязнение PYTHONPATH
- `PYTHONPATH` (session) = `C:\Program Files\PerkinElmerInformatics\ChemOffice2019\ChemScript\Lib`
- Это источник случайных конфликтов импортов у сторонних subprocess-скриптов (ChemOffice идёт раньше системных модулей).

## Что сделано (изоляция)

### a) Создан изолированный venv
- Путь: `<HARNESS>/.venv` (= junction `E:\opencode_harness\.venv`)
- Содержит только pip+setuptools. Без внешних пакетов.
- **Проверено:** импорт state_reducer/contract_validator/provenance/code_factory_runner и memory OK;
  `factory_ctl init/submit/status` и **19/19 unit-тестов** проходят на этом чистом venv.

### b) requirements
- `requirements-core.txt` — ПУСТ намеренно (ядру ничего не нужно).
- `requirements-mcp-doc.txt` — для опционального doc_extract (python-docx, markdownify, pypdfium2, openpyxl).

### c) setup_env.ps1
- `PYTHON`/`PYTHON_BIN` теперь указывают на `<HARNESS>\.venv\Scripts\python.exe`.
- Если venv не найден — fallback на `python` из PATH с предупреждением.

### d) .gitignore
- Создан: игнорит `.venv/`, `venv/`, `.runs/`, `*.db`, `__pycache__`, `.env`.

## Оставшиеся задачи (НЕ выполнены, требуют решения пользователя)

1. **Удалить ChemOffice из PYTHONPATH** (системный/User env) — снимет риск тихих поломок импортов.
   Команда: `[Environment]::SetEnvironmentVariable('PYTHONPATH', $null, 'User')` (и в System, если есть) + рестарт.
2. **doc_extract_server**: решить — либо ставить пакеты в `.venv` (тогда doc_xml заработает), либо
   пометить как неактивный в `mcp_lifecycle_config.json`. Сейчас он зарегистрирован, но нерабочий.
3. **Лишние пакеты hermes-agent venv** — не трогаем: это окружение самого hermes-agent (плейер, не наш).
   Для нашей фабрики главное — HARNESS `.venv` (изолированный).

## Вердикт по ChemOffice (2026-09-06)

**ChemOffice/ChemScript НЕ используется — переносить в HARNESS нечего.**
- `E:\барахло\Documents\Default Project` (researcher-core): 0 упоминаний ChemOffice/ChemScript во всём проекте; зависимости только `PyYAML`.
- HARNESS: химия реализована RDKit-скиллами (`skills/server2-corpus/*`), не ChemOffice.
- `ChemScript19forPy25/26/31/32.pyd` — бинарники для Python 2.5–3.2, несовместимы с Python 3.11.
- `PYTHONPATH` (Machine scope) = `C:\Program Files\PerkinElmerInformatics\ChemOffice2019\ChemScript\Lib` — глобальный мусор, идёт первым в `sys.path`, риск теневых модулей.

**Действие (одобрить):** удалить `PYTHONPATH` из Machine scope + рестарт. ChemOffice сам по себе остаётся установленным, трогаем только переменную среды.

## Как использовать
```powershell
# создать/обновить venv (idempotent)
python -m venv "$env:OPENCODE_HARNESS_ROOT\.venv"
# установить MCP-документы (опционально)
& "$env:OPENCODE_HARNESS_ROOT\.venv\Scripts\pip" install -r "$env:OPENCODE_HARNESS_ROOT\requirements-mcp-doc.txt"
# запуск фабрики на изолированном питоне
& "$env:OPENCODE_HARNESS_ROOT\.venv\Scripts\python" "$env:OPENCODE_HARNESS_ROOT\scripts\code-factory\factory_ctl.py" ...
```