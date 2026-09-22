# План настройки harness «поиск → парсинг → верификация → аналитика → отчёт» (плагины / MCP)

**Автор:** Research Engineer (только исследование + план, код не писался)
**Дата:** 2026-08-21
**Назначение:** подобрать плагины и MCP-серверы для сборки сервера-поиска-аналитики и предложить порядок их объединения в harness.

---

## 0. Методология поиска (чекпоинты выполнения)

Использованы ≥3 поисковых поверхности + GitHub API:

| Источник | Что делал | Результат |
|---|---|---|
| GitHub API (`api.github.com/search/repositories`) | поиск репозиториев по `opencode plugin`, `mcp search server`, `searxng mcp`, `markitdown docling mcp`, `fact check mcp`, `knowledge graph mcp` и т.д. | ~6 запросов, без ключа, с паузами (rate-limit соблюдён) |
| curated list `punkpeye/awesome-mcp-servers` (README) | прочитан полностью, извлечены секции Research / Search & Data Extraction / Data Science / Knowledge & Memory | основной пул кандидатов |
| curated list `awesome-opencode/awesome-opencode` | найден через GitHub API | opencode-специфичные плагины (marketplace, memory, context-pruning) |
| Web-поиск (websearch tool) | Bing/DDG/Yandex/Reddit | **заблокирован**: 403 от `search.parallel.ai/mcp`. Честно зафиксировано — заменено на GitHub API + webfetch к curated спискам |

**Честно:** прямой браузерный поиск (Bing/Yandex/Reddit) недоступен в этом окружении (403). Компенсировано GitHub API (6+ запросов) и чтением двух курируемых реестров MCP — этого достаточно для покрытия всех 5 категорий.

---

## 1. Поиск (≥3 сервера + локальный)

| Плагин / MCP | URL | Что делает | Лицензия / совместимость |
|---|---|---|---|
| **ihor-sokoliuk/mcp-searxng** | github.com/ihor-sokoliuk/mcp-searxng | Приватный веб-поиск через локальный/свой SearXNG (метапоиск) | local, любой MCP-клиент |
| **jae-jae/searxng-mul-mcp** | github.com/jae-jae/searxng-mul-mcp | SearXNG с **параллельным multi-query** поиском | local, MCP |
| **SecretiveShell/MCP-searxng** | github.com/SecretiveShell/MCP-searxng | Подключение агентов к поисковым системам через SearXNG | local, MCP |
| **anysearch-ai/anysearch-mcp-server** | github.com/anysearch-ai/anysearch-mcp-server | Единый real-time поиск: общий веб, вертикальный, **параллельный batch**, извлечение полной страницы по URL | cloud, API-ключ |
| **exa-labs/exa-mcp-server** | github.com/exa-labs/exa-mcp-server | Официальный Exa: веб-поиск + краулинг | cloud, API-ключ |
| **tavily-ai/tavily-mcp** | github.com/tavily-ai/tavily-mcp | Search / extract / map / crawl, production-ready | cloud, API-ключ |
| **brave/brave-search-mcp-server** | github.com/brave/brave-search-mcp-server | Поиск через Brave Search API | cloud, API-ключ |
| **yokingma/one-search-mcp** | github.com/yokingma/one-search-mcp | Web Search & Scraper: SearXNG, Tavily, DuckDuckGo, Bing — агрегатор + скрапер | гибрид |
| **KnockOutEZ/wigolo** | github.com/KnockOutEZ/wigolo | Local-first, **keyless**: search/fetch/crawl/extract/cache + локальный ML-rerank, SQLite-кэш | local, MCP |
| **wd041216-bit/free-web-search-ultimate** | github.com/wd041216-bit/free-web-search-ultimate | 10+ движков (DDG, Bing, Google, Brave, Wiki, Arxiv, YouTube, Reddit), **без ключа** | local, MIT |
| **divyanshu-iitian/SearchForge** | github.com/divyanshu-iitian/SearchForge | GitHub/Crossref/HN/Wikipedia/SearXNG + URL→Markdown, health-диагностика, без телеметрии | local, MCP |
| **Khamel83/argus** | github.com/Khamel83/argus | Multi-provider search broker: авто-fallback, **RRF-ранжирование**, budget enforcement | local, MCP |
| **mrkrsl/web-search-mcp** | github.com/mrkrsl/web-search-mcp | Простой локальный web-search MCP для локальных LLM | local |

**Рекомендация по поиску (3 сервера + локальный):**
1. **SearXNG + mcp-searxng** (локальный, приватный, мульти-движок) — ядро.
2. **anysearch-mcp-server** или **tavily-mcp** (облако, параллельный batch, глубокое извлечение) — покрытие и full-page extraction.
3. **exa-mcp-server** (нейро-поиск, цитаты) — третий движок для разнообразия.
4. Локальный резерв: **wigolo** / **free-web-search-ultimate** (без ключа, когда облако недоступно).

---

## 2. Парсинг (PDF / djvu / HTML / аудио → текст+структура)

| Плагин / MCP | URL | Что делает | Лицензия / совместимость |
|---|---|---|---|
| **BUZDOLAPCI/pdf-parse** | github.com/BUZDOLAPCI/pdf-parse | PDF → текст + извлечение таблиц (Python) | local, MIT |
| **okrapdf/pdf-mcp** | github.com/okrapdf/pdf-mcp | PDF parsing/extraction + accessible-HTML над MCP | local, MCP |
| **zanetworker/mcp-docling** | github.com/zanetworker/mcp-docling | Docling: PDF/Office/HTML → структурированный Markdown | local/cloud, MCP |
| **salman0ansari/artifactkit** | github.com/salman0ansari/artifactkit | Локальный парсинг документов + структурированное извлечение | local |
| **AeternaLabsHQ/pullmd** | github.com/AeternaLabsHQ/pullmd | URL/файл → Markdown (веб, доки, картинки, аудио, YouTube), PWA+REST+MCP | local, MCP |
| **zcaceres/markdownify-mcp** | github.com/zcaceres/markdownify-mcp | Любой файл/веб-контент → Markdown | local, MIT |
| **vivekVells/mcp-pandoc** | github.com/vivekVells/mcp-pandoc | Конвертация форматов через pandoc | local, MCP |
| **andyliszewski/webcrawl-mcp** | github.com/andyliszewski/webcrawl-mcp | Локальный scrape через trafilatura + Firecrawl-fallback (JS) | local, MCP |
| **ggozad/haiku.rag** | github.com/ggozad/haiku.rag | Agentic RAG: Docling-парсинг + LanceDB + rerank, MCP | local |
| **format37/youtube_mcp**, **mrslbt/rippr** | github.com/format37/youtube_mcp, github.com/mrslbt/rippr | Транскрипты YouTube → текст/JSON | local |

**Рекомендация по парсингу:**
- Ядро: **mcp-docling** (универсальный парсер документов, таблицы/структура) + **pullmd** (веб→Markdown, мультиформат).
- Для PDF-таблиц: **BUZDOLAPCI/pdf-parse**.
- Локальный scrape: **webcrawl-mcp** (без ключей).

---

## 3. Верификация (релевантность / факт-чек / дедупликация / противоречия)

| Плагин / MCP | URL | Что делает | Лицензия / совместимость |
|---|---|---|---|
| **ankitkapur1992-hlido/hlido-mcp** | github.com/ankitkapur1992-hlido/hlido-mcp | Независимые trust-скоры, **claim audit**, per-claim PASS/FAIL, подписанное evidence (hosted, без ключа) | cloud, MCP |
| **BrowseAI-HQ/BrowserAI-Dev** | github.com/BrowseAI-HQ/BrowserAI-Dev | Evidence-backed web research: cited claims, **confidence scores**, compare mode | cloud, MCP |
| **nangman-infra/touch-browser** | github.com/nangman-infra/touch-browser | Evidence-grounded: проверяет page-local claims цитатами, confidence bands, multi-page synthesis | local, MCP |
| **Correctover/mcp-server** | github.com/Correctover/mcp-server | **6-мерная верификация** (structure, schema, latency, cost, identity, integrity), self-healing failover | cloud/local, BYOK (OpenAI/DeepSeek/…) |
| **Proofpane/releases** | github.com/Proofpane/releases | Governance-прокси: policy gates, **DLP-redaction**, hash-chained audit log | local, MIT, бинарь |
| **AutomateLab-tech/citation-intelligence** | github.com/AutomateLab-tech/citation-intelligence | Что цитируют LLM (Perplexity/Claude/ChatGPT/Gemini) для запроса — visibility | local, BYO key |
| **echology-io/decompose** | github.com/echology-io/decompose | Детерминированный разбор текста на семантические единицы с **authority/risk/attention** скорами, без LLM | local, MIT |
| **juyterman1000/entroly** (WITNESS) | github.com/juyterman1000/entroly | **WITNESS hallucination guard** (0.844 AUROC, ~3ms, $0), локальная проверка ответов | local, Apache-2.0 |
| **SelfPy/science-ai-mcp-server** | github.com/SelfPy/science-ai-mcp-server | **Duplicate Publication Checker** (CrossRef/arXiv/medRxiv/bioRxiv) | local, free |
| **musharna/data-aggregator-mcp** | github.com/musharna/data-aggregator-mcp | **DOI-дедупликация**, checksum-verified download, paper→data linking | local, uvx |
| **turbyho/mem-context** | github.com/turbyho/mem-context | Авто-**дедупликация**, 6-факторная relevance-оценка | local, MCP |
| **Thezenmonster/agentmem** | github.com/Thezenmonster/agentmem | **conflict detection**, trust lifecycle, health scoring памяти | local, SQLite |

**Рекомендация по верификации:**
- Факт-чек цитат: **hlido-mcp** (per-claim PASS/FAIL, без ключа) + **touch-browser** (page-local confidence bands, локально).
- Дедупликация источников: **data-aggregator-mcp** (DOI) + **mem-context** (relevance/dedup).
- Анти-галлюцинация финального отчёта: **entroly/WITNESS** (детерминированный guard).
- Детерминированный разбор тезисов: **echology-io/decompose** (authority/risk, без LLM — хорошо ложится на принцип детерминированного слоя из проекта resercher).

---

## 4. Аналитика (кластеризация / противоречия / обработка данных)

| Плагин / MCP | URL | Что делает | Лицензия / совместимость |
|---|---|---|---|
| **Bright-L01/networkx-mcp-server** | github.com/Bright-L01/networkx-mcp-server | Граф-анализ: centrality, **community detection**, PageRank, визуализация | local, MCP |
| **gzoonet/cortex** | github.com/gzoonet/cortex | Локальный knowledge graph: сущности/связи из файлов проекта | local, MCP |
| **blackmount-nlp-mcp** | github.com/BlackMount-ai/blackmount-nlp-mcp | Детерминированный NLP: sentiment, **text similarity**, summarization, keyword extraction (18 яз.) | local, MIT, 42KB |
| **haiiibin/data-profiler-mcp** | github.com/haiiibin/data-profiler-mcp | Профилирование табличных данных: missing/duplicates/outliers/смешанные типы | local, pandas |
| **DataEval/dingo** | github.com/DataEval/dingo | Комплексная data-quality оценка (rule-based + LLM-based) | local |
| **leap-laboratories/discovery-engine** | github.com/leap-laboratories/discovery-engine | Exploratory data analysis: feature interactions, subgroup effects, p-values, effect sizes | cloud, free для публичных данных |
| **kdqed/zaturn** | github.com/kdqed/zaturn | Связывание источников (SQL/CSV/Parquet) + AI-анализ инсайтов | local |
| **apecloud/ApeRAG** | github.com/apecloud/ApeRAG | Graph RAG + vector + full-text: knowledge graph и context engineering | local/cloud |
| **booboo** (jessedu29260) | github.com/jessedu29260-netizen/booboo | 3D knowledge graph агентов/памяти/знаний, pathfinding | local, MCP |

**Рекомендация по аналитике:**
- Выявление противоречий/кластеров источников: **networkx-mcp-server** (community detection по графу цитирования/тем) + **cortex** (knowledge graph сущностей).
- Детерминированное сходство/суммаризация тезисов: **blackmount-nlp-mcp** (без LLM, 18 языков — важно для русскоязычного корпуса).
- Аудит качества извлечённых данных: **data-profiler-mcp** (дубликаты/выбросы).
