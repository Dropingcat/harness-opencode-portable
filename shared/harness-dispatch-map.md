# Harness Dispatch Map — карта «задача → контур → инструмент»

Единый маршрутизатор для агента: какую задачу каким контуром и инструментом решать.
Читать ПЕРЕД началом любой задачи. Это исключает путаницу «верификация vs сбор vs поиск».

## Шаг 0: Определи тип задачи (3 контура)

| # | Тип задачи | Контур | Оркестратор (primary) | Что делает |
|---|---|---|---|---|
| 1 | Верифицировать научный текст (клаймы→источники→вердикты→отчёт) | **research** | `research-orchestrator` | Запускает `run_research.py` (BRICKS-цикл) |
| 2 | Найти/собрать источники по списку (статьи, DOI, монографии) | **research** | `research-orchestrator` | `downloader.py` + source-fetcher (статьи) / gost-сбор (нормативка) |
| 3 | Написать статью/отчёт/рерайт | **writer** | `writing-orchestrator` | writer-core: план→черновик→DOM→review |
| 4 | Реализовать/починить/проревьюить код | **coder** | `code-orchestrator` | coder-factory: worker→reviewer→tester |
| 5 | Управлять техдолгами/реестром | **coder** | `code-orchestrator` | `tech_debt_cli.py` (не ad-hoc скрипты!) |
| 6 | Семпоиск по локальному корпусу | **research** | research-orchestrator | `chroma_indexer.py search` |

## Шаг 1: Инструменты (канонические, из `scripts/tools/`)

**НЕ пиши ad-hoc скрипты в C:\Temp\opencode. Используй готовые:**

| Инструмент | Когда | Команда |
|---|---|---|
| `tech_debt_cli.py` | add/close/update/get/list/next долгов; регенерация мастера | `python scripts/tools/tech_debt_cli.py <cmd> ...` |
| `sync_tech_debt.py` | после правки долгов — синхронизация portable/work | `python scripts/tools/sync_tech_debt.py [--dry-run] [--backup]` |
| `downloader.py` | скачать статью по DOI (CrossRef+Sci-Hub), URL, извлечь текст PDF | `downloader.py doi --doi ... --out ...` / `url` / `extract --pdf ...` |
| `session_analyzer.py` | разобрать opencode-сессию (dump/tools/errors/writes/text) | `python scripts/tools/session_analyzer.py <cmd> <session.json>` |
| `chroma_indexer.py` | индекс/поиск по локальному корпусу (ChromaDB) | `python scripts/tools/chroma_indexer.py search --query "..."` |

## Шаг 2: Поиск источников — порядок (жёсткий)

1. **Локальный корпус** (ChromaDB): `chroma_indexer.py search --query "<claim/термин>"`
2. **arXiv/OpenAlex** (research_papers MCP / source-fetcher)
3. **Веб** (browser-MCP / webfetch / SearXNG **если поднят**)
4. DOI → **CrossRef-gate** → `downloader.py doi` (Sci-Hub)

> SearXNG (`127.0.0.1:8888`) — НЕ поднят (нет Docker). TD-128. Не жди его: используй browser-MCP/webfetch напрямую.

## Шаг 3: Блоки/долги — где смотреть

- Канонический реестр: `E:\opencode_harness_portable\config\tech_debt.json` (portable = источник правды, work = зеркало)
- Пространства ID: `TD-*` (архитектура harness), `RS-*` (исследовательские, из work)
- Быстрый список: `python scripts/tools/tech_debt_cli.py list --status open`

## Шаг 4: Runner (верификация текста)

`run_research.py` (Python, кросс-платформенный) — для задачи «верифицировать текст» (BRICK 1-10).
Промпты агентов: `python scripts/tools/session_analyzer.py` для разбора.
Dry-run: `--dry-run` (агенты не вызываются).

## Анти-путаница (checklist перед стартом)

- [ ] Я знаю тип задачи (1-6) и контур?
- [ ] Я использую канонический инструмент (tools/) а не пишу новый скрипт?
- [ ] Я знаю, что SearXNG недоступен (TD-128) и ищу через browser-MCP/webfetch?
- [ ] Для сбора нормативки (ГОСТ/ТУ) — это source-collection, НЕ полный BRICKS-цикл (TD-122)?
- [ ] Техдолги — через `tech_debt_cli.py`, не вручную?