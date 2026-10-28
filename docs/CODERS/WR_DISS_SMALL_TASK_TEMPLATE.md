# WR-DISS — шаблон контракта мелкой задачи по диссертации (writer-контур)

Адаптация `15_GENERAL_HANDS.md` (руки оркестратора) под письменные задачи диссертации.
Образцы заполнения: `WR_DISS_ARCHIVE_SOURCES_20261019.md`, `WR_DISS_INTRO_VAK_20261019.md`.

## Запуск (PowerShell 5.1, из корня harness)

```powershell
$oc = "C:\Users\Arhys\AppData\Local\Programs\@opencodedesktop\resources\opencode-cli.exe"
Set-Location E:\opencode_harness_portable
& $oc run --agent <агент> --auto --title "<WR-ID>" --file "<путь к контракту>.md" "Выполни контракт из приложенного файла полностью. Финальный отчёт — по секции «Контракт выхода»."
```

## Выбор агента

| Задача | Агент | Скиллы (загрузить через `skill`) | MCP / инструменты |
|---|---|---|---|
| Реквизиты, BIB-карточки, сверка ссылок | `general` (руки); при чистой проверке списка — `reference-auditor` | `citation-management`, `claim-boundary-checker` | `academic-search` (verify_reference/_batch), `doc_extract`; `scripts/tools/downloader.py extract`, `book_finder.py verdict` |
| Подбор источников под тезис | `source-fetcher` / `general` | `literature-review`, `research-lookup` | `chroma_indexer.py search` (только count/search), `academic_search`, `searxng_search` |
| Проверка утверждений в тексте | `fact-checker` / `claim-parser` | `claim-boundary-checker`, `scientific-critical-thinking` | `scripts/researcher/verify_claims.py`, `scripts/writer/citation_trace.py` |
| Черновик/правка абзаца | `article-writer` | `writer-core`, `scientific-writing`, `ai-slop-avoidance`, `writing-enforcer` (DETECT) | `wc_cli.py draftcheck/review`, `draft_loop.py` |
| Терминология | `general` | `glossary-registry` | — |

## Тело контракта

```text
# <WR-ID> · <дата> · <оркестратор> → <агент>

## Задача
<что и зачем, 2–4 строки; решение автора, на которое опирается задача>

## Контракт входа
- Читать (не изменять): <пути>
- Защищённые файлы (sha256 до/после): <пути>
- Текущее состояние: <что есть>

## Скиллы и инструменты
- Загрузить скиллы: <...>
- MCP/CLI: <...>; читать `shared/harness-dispatch-map.md` перед стартом.
- Не писать ad-hoc скрипты, если есть канонический инструмент.

## Шаги
1. ...

## Контракт выхода (писать только в <OUT_DIR>)
1. <артефакт> — <формат>
2. RESULT.md / RESULT.json — вердикт PASS | PARTIAL | BLOCKED | FAIL + перечень недостающего
3. Проверки: таблица «проверка → команда → ожидание → факт → PASS/FAIL»
4. Техдолги/находки — перечислить, не регистрировать

## Правила
- Ничего не выдумывать: каждое поле — с каналом подтверждения; нет подтверждения → «не установлено» + причина.
- Временные файлы — только в <OUT_DIR>\_tmp или E:\opencode_harness_portable\tmp. Не использовать C:\ и C:\Temp.
- Без git-операций, без правки мастер-реестров/DOM/автореферата/текста главы.
- Самоцитирования автора (Черенков, Александрова, Винтайкин) в BIB не заводить.
- При недоступности канала — зафиксировать попытки и вернуть BLOCKED, не имитировать результат.
- Вывод любого инструмента ≤ ~200 КБ (иначе CLI падает с SseEventTooLarge): без glob/grep по целым дискам, большие файлы — частями, большие выводы — в файл и читать частями.
```

## Chroma (семантический поиск по корпусу F:\AnalisysDataSet) — РАБОТАЕТ
Коллекция `papers`, 16 211 чанков (проверено 26.10.2026). CLI сам перезапускается в venv hermes, где установлен chromadb (строка `INFO: chromadb нет в текущем python, перезапуск…` — это норма, не ошибка):
```powershell
$py="E:\opencode_harness_portable\.venv\Scripts\python.exe"; $ci="E:\opencode_harness_portable\scripts\tools\chroma_indexer.py"
& $py -X utf8 $ci --db F:\AnalisysDataSet\.chroma_papers --collection papers search --query "<запрос>" -n 10
```
Только `count`/`search`; `index`/`reset` запрещены. Выдача — фрагменты .md из `F:\AnalisysDataSet\02-Methods\` (путь файла в поле `file=`); найденный фрагмент — указатель, цитировать по исходному файлу.

## Если агент упал (SseEventTooLarge и т.п.)
Сделанное сохраняется в сессии. Найти id: `& $oc session list`, затем продолжить:
`& $oc run --session <ses_id> --agent <агент> --auto "Продолжи контракт с места остановки; <что учесть>"`
