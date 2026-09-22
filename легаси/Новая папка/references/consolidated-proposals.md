# Консолидированный список предложений (сессия 2026-08-21 + отчёты)

Собрано из диалога и отчётов в doc_hermes_pi. Группировка по направлениям.

---

## 1. Единый MCP «coder-researcher» (главное направление)
**Предложение Ярослава:** один MCP-сервер, который оркестратор активирует для задачи поиска-анализа. Внутри — кодер + его внутренние MCP/плагины, описанные как КОНТРАКТЫ.

```
[оркестратор] → активирует → [MCP coder-researcher]
   ПОИСК:    search(query, engines=[yandex,bing,ddg,reddit,searxng,arxiv,openalex], pages) → ≥3 сервера
   ПАРСИНГ:  fetch / extract_text / pdf_to_text / djvu / визуальный (OpenCV/ShowUI)
   ВЕРИФИКАЦИЯ: релевантность (supports/context) + dedup + trust
   АНАЛИТИКА: кластеризация / сводка / противоречия
   ОТЧЁТ:    тезис + цитата из источника + источник → report.md
```
Рамка кодера: только «поиск и сбор информации» → отчёт. Не кодинг.

**Кластеры + отдельный MCP для оркестратора:**
- free → hy3-free (✅ работает)
- polza → deepseek-v4-flash-0731 (✅, 23₽)
- antigravity → Claude Opus/Gemini 3 (вскоре, noefabris/opencode-antigravity-auth 11K★)

## 2. Проблема с точностью/автоматизацией (урок)
**Признано:** я упрощаю ТЗ, выкидывая контекст. Скилл не лечит — нужен **фиксированный контракт** в MCP/коде, а не мои слова в промте. Контракт даёт кодеру на что опереться, какие инструменты использовать. Демонстрация: поиск «дозы удобрений малины» по ≥3 серверам дал yandex+ddg релевантное, bing мимо — контракт обязывает брать ≥3, не полагаться на один.

## 3. Плагины/MCP для harness (из отчёта кодера — реальные репо)
### Поиск
- mcp-searxng, searxng-mul-mcp, MCP-searxng (локальный SearXNG)
- anysearch-mcp, exa-mcp, tavily-mcp, brave-search-mcp (облако, ключи)
- one-search-mcp (SearXNG/Tavily/DDG/Bing агрегатор+скрапер)
- wigolo (keyless, local-first, SQLite-кэш)
- free-web-search-ultimate (10+ движков без ключа, MIT)
- SearchForge (GitHub/Crossref/HN/Wiki/SearXNG, без телеметрии)
- argus (multi-provider broker, RRF, budget)
### Парсинг
- mcp-docling (PDF/Office/HTML → Markdown)
- pullmd (url/файл → Markdown)
- pdf-parse (PDF → текст+таблицы)
- markdownify-mcp, mcp-pandoc, webcrawl-mcp (trafilatura, без ключей)
### Верификация
- hlido-mcp (claim audit, per-claim PASS/FAIL, без ключа)
- touch-browser (page-local confidence bands)
- entroly/WITNESS (анти-галлюцинация, 0.844 AUROC, $0)
- echology-io/decompose (детерм. разбор, authority/risk, без LLM — ложится на принцип №0)
- data-aggregator-mcp (DOI-дедуп), mem-context (relevance/dedup)
### Аналитика
- networkx-mcp-server (community detection)
- cortex (knowledge graph)
- blackmount-nlp-mcp (18 языков, без LLM)
- data-profiler-mcp (duplicates/outliers)
- ApeRAG (Graph RAG + vector)

## 4. Капсулы поиска (готово/статус)
| Капсула | Статус |
|---|---|
| browser-mcp (fetch/search/extract/reddit) | ✅ работает |
| Яндекс-поиск + browser_evidence (тезис→цитаты) | ✅ работает |
| Bing plain HTTP (обход Google-блока) | ✅ работает |
| Google | ❌ блок автоматизации (не IP) — нужна симуляция человека/UI-агент |
| Reddit (pullpush) | ⚠️ деградировал (429, платный для агентов) |
| SearXNG | в плане (поднять локально) |
| VPN-туннель VNNet | todo (обход DPI/rate-limit) |

## 5. Обход анти-бот Google (результаты)
- Google блокирует автоматизацию (fingerprint), не IP
- Playwright stealth/persistent/жесты/Xvfb — все ❌ reCAPTCHA
- Рабочий обход: Bing plain HTTP
- Следующие шаги: **симуляция человека** (мышь/клавиатура/паузы — реализовано), **визуальная детекция** (OpenCV — работает, ShowUI 2B — в плане), **UI-агенты** (Bogdan XST/UI-TARS/ShowUI/Agent S/OpenCV — todo ui-agent-chain)

## 6. Итеративный поисковый контур (todo)
- генерация/ротация RU+EN запросов → поиск по всем движкам → парсинг → оценка релевантности → обратная связь (уточнить) → отчёт
- большой охват (КиберЛенинка/книги/форумы/ResearchGate/GitHub) как «большое сито» + единый отсев

## 7. Инструментальный маршрутизатор (стратегический урок)
- Выбирать инструмент ПО КЛАССУ ЗАДАЧИ, а не по доступности (научная литература → arXiv/OpenAlex/корпус, а не веб)
- Маршрутизаторы-аналоги: claude-code-router (36K★), dify (153K★), spring-ai-tool-search
- Двухъярусная архитектура: Ярус 1 = глоссарий «клейм→инструмент» (reflection-gate), Ярус 2 = делегирование кодеру с шаблоном маршрутизации

## 8. Free-модели кодера (проверено)
- opencode/deepseek-v4-flash-free — СНЯТА (пропала из списка)
- **hy3-free** — ✅ стабильный бесплатный кодер (пишет код, запускает python)
- x-preview-f-free — нестабильна
- nemotron/mimo-free — виснут
- Qwen-веб-сессия (ai-free/FreeQwenApi) — запасной бесплатный LLM-транспорт

## 9. Верификация resercher (техдолг из ревизии)
- document_text не используется (анти-циркулярность не на этапе 3) — P0
- потеря контекста (V%/метод/единицы) для LLM-фаз — P0
- контракты-схемы + input_hash, единый id-маппер
- прокинуть числовой блок в судей/рецензентов

## 10. GPT Researcher (готово)
- установлен, на Polza, CLI-обёртка gptr_research.py
- рабочий ретривер — arxiv (+openalex когда 429 спадёт)
- контекст-инжекшен вместо conduct (обход 414)
- --context-file — техдолг P0

## 11. Провайдеры/транспорт
- единый provider_config.yaml — заменить жёсткие aitunnel/polza (todo)
- ai-free/FreeQwenApi — бесплатный LLM через веб-сессию (todo)
- баланс Polza 23₽ (иссякает) — экономить, free-hy3 основной

---

## Приоритеты (предложение)
1. **MCP coder-researcher** (скелет: единый MCP + кластеры free/polza) — основа автоматизации
2. **Верификация-плагины** (hlido/WITNESS/echology) — сильнейший прирост качества
3. **hy3-free как дефолт кодера** (заменить снятую deepseek-free)
4. SearXNG локально (свой метапоиск, 0 ключей)
5. Симуляция человека для Google + ShowUI 2B (визуальный парсинг)
6. Инструментальный маршрутизатор (глоссарий клейм→инструмент)
