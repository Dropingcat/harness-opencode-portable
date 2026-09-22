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

**Шаблоны контрактов — в роутере.** `harness_run`/`resolve_bundle` возвращает `templates` (13 шт.): `arxiv_search`, `openalex_search`, `extract_document`, `searxng_search`, `sci_bot`, `downloader_doi`, `downloader_resolve`, `downloader_dns`, `gost_collector`, `code_work`, `literature-review`, `profile_config`, `customize-opencode`. Каждый шаблон содержит: команду, required_input, forbidden_input, start_with/finish_with, guard. **Не выдумывай вызов — возьми шаблон из bundle.**

**НЕ пиши ad-hoc скрипты в C:\Temp\opencode. Используй готовые:**

| Инструмент | Когда | Команда |
|---|---|---|
| `tech_debt_cli.py` | add/close/update/get/list/next долгов; регенерация мастера | `python scripts/tools/tech_debt_cli.py <cmd> ...` |
| `sync_tech_debt.py` | после правки долгов — синхронизация portable/work | `python scripts/tools/sync_tech_debt.py [--dry-run] [--backup]` |
| `downloader.py` | скачать статью по DOI (CrossRef+Sci-Hub), URL, извлечь текст PDF | `downloader.py doi --doi ... --out ...` / `url` / `extract --pdf ...` |
| `session_analyzer.py` | разобрать opencode-сессию (dump/tools/errors/writes/text) | `python scripts/tools/session_analyzer.py <cmd> <session.json>` |
| `chroma_indexer.py` | индекс/поиск по локальному корпусу (ChromaDB) | `python scripts/tools/chroma_indexer.py search --query "..."` |
| `dom_builder.py` | детерминированный билдер research-DOM/артефактов (TD-143) | `dom_builder.py update-claim --claim c0 --citations "[...]"` / `sync-citations --cmap citations_map.json` / `report` / `verify` / `stats` |
| `gost_collector.py` | сбор ГОСТов/ТУ по маппингу марок (TD-122..125) | `gost_collector.py registry` / `collect --mark ВКС-10` / `backfill` / `provenance --gost 5632-2014` |
| `downloader.py url` | универсальный загрузчик: PDF с проверкой типа, retry, провенанс | `downloader.py url --url ... --out ... --name f.pdf --expect pdf` |
| `downloader.py resolve` | каскадный DOI→PDF: локальный корпус→CrossRef/OpenAlex→openAccessPdf→Sci-Hub→wayback (TD-152) | `downloader.py resolve --doi "10.1007/..." --out ...` |

## Шаг 2: Поиск источников — порядок (жёсткий)

1. **Локальный корпус** (ChromaDB): `chroma_indexer.py search --query "<claim/термин>"`
2. **arXiv/OpenAlex** (research_papers MCP / source-fetcher)
3. **Веб** (browser-MCP / webfetch / SearXNG **если поднят**)
4. DOI → **CrossRef-gate** → `downloader.py doi` (Sci-Hub)

> SearXNG (`127.0.0.1:8888`) — НЕ поднят (нет Docker). TD-128. Не жди его: используй browser-MCP/webfetch напрямую.
>
> **MCP-серверы** (arxiv_search/openalex_search/extract_document/searxng_search) подключены в `.opencode/.mcp.json` (генератор `scripts/router/gen_mcp_config.py`), но видны субагентам только ПОСЛЕ РЕСТАРТА opencode (MCP инжектятся при старте сессии). TD-155. Резервный канал (работает всегда): `webfetch` → `https://export.arxiv.org/api/query?search_query=...` / `https://api.openalex.org/works?search=...`.

## Sci-Bot — это API, не GUI (TD-156)

Sci-Bot (sci-bot.ru) — **программный API** (WebSocket `wss://sci-bot.ru/`), НЕ приложение с Linux/X11. Вызывается напрямую:
```
python C:\Users\Arhys\.config\opencode\skills\sci-bot\scripts\sci_bot_client.py --help
```
- Баланс: `python ...\sci_bot_client.py balance`
- Запрос статей (conversation, ~20K токенов): `python ...\sci_bot_client.py ask "<тема>" --conv`
- Скилл: `skill` → `sci-bot` (стоимость, ограничения: не open-ended, не полные тексты)
НЕ пиши «требует Linux/ручной запуск» — вызывай клиент через bash.

## Капча sci-hub (TD-158)

Если sci-hub вернул «проверка на робота» (Cloudflare/captcha): НЕ сдавайся. Маршрут: (1) повтори с cookie/UA, (2) sci-bot API (conversation-режим — он обходит капчу), (3) `downloader.py doi` повторно, (4) честно пометь «требует ручного скачивания» с DOI. Зафиксируй блок через `tech_debt_cli.py auto` если повторяется.

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
- [ ] DOM/артефакты (ch1_dom.json, citations_map, отчёты) — через `dom_builder.py`, не ad-hoc скриптами? (TD-143)
- [ ] Семпоиск — через `chroma_indexer.py`, не вручную? (TD-142)

## Авто-фиксация блока (TD-144) — зафиксировать за 1 шаг

Столкнулся с блоком (сломалось, мешает, повторяется)? **НЕ пиши вручную поля. Вызови:**

```
python scripts/tools/tech_debt_cli.py auto --desc "<что случилось, почему мешает>" [--llm]
```

- Эвристика сама определит kind/severity/owner по описанию
- `--llm` — дополнительно оформит через LLM-диспатч (notes/acceptance)
- `--id TD-XXX` — если нужен конкретный ID (иначе следующий свободный)
- После: `python scripts/tools/sync_tech_debt.py`

**Или** просто скажи оркестратору «зафиксируй блок: <описание>» — роутер сам направит на tech-debt маршрут (agent=code-orchestrator), тот вызовет `auto`.

## Паттерн-аудитор (TD-145) — повторяющиеся действия

Если ты (или другой агент) делаешь одно и то же 3+ раз (пишешь похожий ad-hoc скрипт, вручную ищешь, переписываешь):

1. **Сначала** — попробуй канонический инструмент (tools/): возможно он уже есть.
2. **Нет инструмента?** Зафиксируй через `auto --desc "повторяется: <что>"` — это станет техдолгом оптимизации.
3. **Диагностику повторов** делай через: `python scripts/tools/session_analyzer.py tools <session.json>` (частые инструменты/ошибки).

Роутер: задача «аудитор проверь повторы» → tech-debt/opencode-config маршрут → code-orchestrator → session_analyzer + техдолг оптимизации.

## Просмотр сессий агентов (TD-150) — oc://renderer

Чтобы посмотреть, что реально сделал агент (в т.ч. субагент в отдельной ветке opencode), используй **renderer-ссылку сессии**:

```
oc://renderer/server/<server-id>/session/<session-id>
```

- **server-id** — идентификатор opencode-сервера (например `c2lkZWNhcg`)
- **session-id** — id сессии (например `ses_f35d789d1ffeerjnBq3Mzs4vmg`)
- Формат открывает сессию в интерфейсе opencode (renderer), где видна вся ветка сообщений агента — включая субагентские вызовы, ошибки, артефакты.

**Как узнать id:**
- Текущая сессия: `oc://renderer/server/<server-id>/session/<текущий-id>` — id виден в начале сессии (при старте) или в логе.
- Субагентская: при падении субагента (task) его сессия живёт во вложенной ветке; renderer-ссылка на неё открывается из родительской сессии (клик по задаче/ветке) или из лога `storage/session_diff/`.

**Когда использовать (TD-150):** субагент упал → НЕ гадай «ничего не сделал» — открой его сессию через renderer-ссылку, посмотри stdout/stderr/артефакты. Если ссылка не доступна — прочитай сессию через `session_analyzer.py dump <session.json>`.