# ПЛАН: Архитектура Hermes Default-профиля — Router → Delegate → OpenCode

**Дата:** 2026-08-22
**Автор:** Алиса (на основе анализа сессии opencode от 21.08 + документов кодера)
**Статус:** ГОТОВ К ВНЕДРЕНИЮ (этап 1 — неразрушающие изменения)

---

## Контекст сессии 21.08

Пользователь (Ярослав) в сессии opencode `ses_fdaac3e37ffeX0LH6klld8h5bo` поставил задачи:
1. Ревизия `/home/orangepi/Документы/`, `doc_alisa_assistant/`, `/home/orangepi/.hermes/`
2. Анализ архитектуры default-профиля (сдержки/противовесы, автоматизация, упрощение промтов)
3. Разбор SQL-базы сессий Hermes за день, глобальные предложения
4. Многоступенчатая роутер-система: входные ворота → делегаты со своими MCP и скилами
5. Настройка обоих агентов (default = data analyst / research, alisa = productivity)
6. Поиск модулей на гите для opencode (поиск/парсинг/верификация/аналитика)
7. Composio MCP подключён
8. Завести задачи в трекер и начать внедрение

Кодер **сделал**: прочитал все конфиги, создал 3 плана (`coder-mcp-router-plan.md`, `coder-harness-plugins-plan.md`, `consolidated-proposals.md`), инвентаризировал плагины с GitHub.
Кодер **не сделал**: единый DOC-0 (застрял в цикле `apply_patch` — 500+ ошибок), не внедрил ничего в конфиги.

---

## Текущее состояние default-профиля

**Конфиг:** `/home/orangepi/.hermes/config.yaml`
- Модель: `deepseek-v4-flash:cloud` (ollama-cloud), fallback → aitunnel
- Toolsets: `hermes-cli`, `web`
- MCP servers: `polza-ai` (remote), `browser` (local)
- Профиль запускается через systemd `hermes-gateway.service` (без `--profile`), watchdog каждые 2 мин

**SOUL.md:** `/home/orangepi/.hermes/SOUL.md` (105 строк)
- Роль: «Фёдор» — оценщик неопределённости
- Содержит ручные сдержки: метрики U, пороги 0.1/0.15/0.4, 3 альтернативных ответа
- Проблема: **перегружен ручными правилами** → медленный, требует упрощения

**Prisms:** `claim`, `deep_scan`, `error_resilience`, `identity`, `l12`, `optimize`, `simulation`

**Skills:** большой набор (agent-security, deliberation-engine, deslop, devops, diagramming, и т.д.)

---

## Целевая архитектура

```
┌─────────────────────── HERMES DEFAULT (оркестратор) ──────────────────────┐
│                                                                           │
│  SOUL.md (упрощённый):                                                    │
│    - Роль: research/data-analyst (как Perplexity)                         │
│    - Убрать ручные метрики U → авто-верификация через MCP                  │
│    - Чёткие контракты вместо простыня промта                               │
│                                                                           │
│  Маршрутизатор (reflection-gate):                                         │
│    Ярус 1: глоссарий «класс задачи → инструмент»                           │
│    Ярус 2: делегирование кодеру (opencode) с шаблоном                     │
│                                                                           │
│  MCP servers:                                                             │
│    ├── coder-router (НОВЫЙ) — вызывает opencode run по классу задачи      │
│    ├── browser (существует) — веб-поиск/извлечение                         │
│    ├── polza-ai (существует) — LLM-запросы                                  │
│    ├── composio (ПОДКЛЮЧИТЬ) — GitHub/Slack/Gmail/Calendar                 │
│    └── research-harness (НОВЫЙ, этап 2) — поиск→парсинг→верификация       │
│                                                                           │
│  OpenCode (кодер, вызывается через MCP):                                  │
│    ├── Модель: openai/gpt-5.5-fast (через VNNET прокси wrapper)            │
│    ├── Composio MCP — внешний toolkit                                     │
│    └── oh-my-opencode-slim — набор плагинов                                │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## ЭТАП 1 — Неразрушающие изменения (ВНЕДРЯТЬ ПЕРВЫМ)

### 1.1 Упростить SOUL.md

**Файл:** `/home/orangepi/.hermes/SOUL.md`

**Что изменить:**
- Убрать многоступенчатую систему метрик неопределённости (разделы 1-6 «Оценщик», «Контролёр»)
- Заменить на компактную роль: «research/data-analyst, анти-сикофант, проверяй факты через инструменты»
- Оставить: анти-сикофантизм, «не додумывай», «не упрощай задачу», git-запрет
- Добавить: «для сложных задач — делегируй кодеру через MCP coder-router»
- Добавить: «поиск → через browser MCP или research-harness, не через ручной web_search»

**Цель:** сократить SOUL.md с 105 до ~40 строк, убрать ручные пороги U → авто-верификация.

### 1.2 Создать MCP coder-router

**Новый файл:** `/home/orangepi/.hermes/mcp/coder_router_server.py`

**Интерфейс (tools):**
```python
coder_run(task: str, model_class: str = "free", workdir: str = "/home/orangepi", files: list = []) -> dict
# model_class: "free" → gpt-5.5-fast, "polza" → deepseek-v4-flash, "antigravity" → (future)
# Запускает: /home/orangepi/.opencode/bin/opencode run --pure task
# Возвращает: {stdout, exit_code, artifacts_path}

coder_models() -> list  # доступные модели по классам
coder_status() -> dict   # статус прокси/модели
```

**Логика:**
- Запуск через wrapper `/home/orangepi/.opencode/bin/opencode` (уже настроен с VNNET прокси)
- Модель выбирается из конфига MCP, не из промта
- Timeout: 300с (для длинных задач)
- Output парсится, артефакты сохраняются в `/tmp/opencode/artifacts/`

### 1.3 Подключить MCP в config.yaml

**Файл:** `/home/orangepi/.hermes/config.yaml`

**Добавить в `mcp_servers`:**
```yaml
  coder-router:
    command: "/home/orangepi/.hermes/venvs/hermes-mcp/bin/python"
    args: ["/home/orangepi/.hermes/mcp/coder_router_server.py"]
    timeout: 300
    connect_timeout: 60
```

### 1.4 Подключить Composio MCP

**Файл:** `/home/orangepi/.hermes/config.yaml`

**Добавить в `mcp_servers`:**
```yaml
  composio:
    url: "https://connect.composio.dev/mcp"
    headers:
      x-consumer-api-key: "REDACTED-SET-VIA-ENV"
    timeout: 120
    connect_timeout: 30
```

### 1.5 Smoke-тесты (без перезапуска gateway)

1. `python -c "import yaml; yaml.safe_load(open('/home/orangepi/.hermes/config.yaml'))"` — валидность YAML
2. Запуск coder-router MCP standalone: `python /home/orangepi/.hermes/mcp/coder_router_server.py` — проверка что стартует
3. `opencode run 'echo test' --pure` через wrapper — проверка что кодер отвечает
4. После тестов — перезапуск gateway: `systemctl --user restart hermes-gateway.service`

---

## ЭТАП 2 — Research harness (после этапа 1)

### 2.1 Локальный SearXNG

- Поднять SearXNG в Docker (или без — через pip)
- Подключить `mcp-searxng` к Hermes

### 2.2 MCP research-harness

**Новый файл:** `/home/orangepi/.hermes/mcp/research_harness_server.py`

**Конвейер:**
```
search(query, engines) → fetch/extract → verify(dedup, relevance) → analyze(cluster, summarize) → report.md
```

**Плагины (из отчёта кодера):**
- Поиск: SearXNG (локальный) + wigolo/free-web-search-ultimate (резерв без ключей)
- Парсинг: mcp-docling (PDF/Office/HTML → Markdown) + pullmd (URL → Markdown)
- Верификация: hlido-mcp (claim audit) + entroly/WITNESS (анти-галлюцинация)
- Аналитика: networkx-mcp-server (community detection) + blackmount-nlp-mcp (NLP без LLM)

### 2.3 Инструментальный маршрутизатор

**Новый prism:** `/home/orangepi/.hermes/prisms/route.md`

**Логика:**
- Научная литература → arxiv/openalex (не веб-поиск)
- Веб-поиск → SearXNG (не Google напрямую)
- Кодинг → делегирование coder-router
- Факт-чек → hlido/WITNESS
- PDF → docling

---

## ЭТАП 3 — Оптимизация (после этапа 2)

### 3.1 Унификация провайдеров

- Единый `provider_config.yaml` — заменить жёсткие `aitunnel`/`polza` в конфигах
- Баланс: free (gpt-5.5-fast) как основной, polza (deepseek) как fallback

### 3.2 Авто-верификация

- Заменить ручные пороги U из SOUL.md на:
  - entroly/WITNESS для ответов
  - hlido-mcp для факт-чекинга
  - echology-io/decompose для разбора тезисов

### 3.3 Proxy в systemd

- Добавить proxy env vars в `hermes-gateway.service` (Environment=ALL_PROXY=...)
- Чтобы gateway видел прокси без wrapper

---

## СТОП-УСЛОВИЯ

- ❌ Не трогать `alisa-assistant` профиль (работающий, не ломать)
- ❌ Не запускать opencode в TUI режиме (только `opencode run --pure`)
- ❌ Не править боевые конфиги без бэкапа
- ❌ Не коммитить в git без подтверждения пользователя
- ❌ Не убивать gateway процессы

---

## ИСТОЧНИКИ

- `coder-mcp-router-plan.md` — архитектура coder-router MCP
- `consolidated-proposals.md` — консолидированные предложения (10 пунктов)
- `coder-harness-plugins-plan.md` — каталог плагинов (поиск/парсинг/верификация/аналитика)
- `automation-design.md` — дизайн автоматизации
- `/home/orangepi/.hermes/SOUL.md` — текущий SOUL (перегружен)
- `/home/orangepi/.hermes/config.yaml` — текущий конфиг default-профиля
- Сессия opencode `ses_fdaac3e37ffeX0LH6klld8h5bo` (21.08, 166 сообщений, 1478 parts)

---

## ЗАДАЧИ ДЛЯ ВНЕДРЕНИЯ (канбан)

| # | Задача | Этап | Стоп |
|---|--------|------|------|
| 1 | Упростить SOUL.md (105→40 строк) | 1.1 | Не ломать alisa |
| 2 | Создать MCP coder-router | 1.2 | Только opencode run --pure |
| 3 | Подключить coder-router + composio в config.yaml | 1.3-1.4 | Бэкап конфига |
| 4 | Smoke-тесты | 1.5 | Без перезапуска gateway |
| 5 | Поднять SearXNG локально | 2.1 | Docker или pip |
| 6 | Создать research-harness MCP | 2.2 | Контракты, не промты |
| 7 | Инструментальный маршрутизатор (prism) | 2.3 | Глоссарий клейм→инструмент |
| 8 | Унификация провайдеров | 3.1 | provider_config.yaml |
| 9 | Авто-верификация (WITNESS/hlido) | 3.2 | Замена ручных порогов |
| 10 | Proxy в systemd units | 3.3 | Environment= |

---

## ПРИОРИТЕТ

**Этап 1 — сделать немедленно** (неразрушающие, бэкапы обязательны)
**Этап 2 — после проверки этапа 1** (research harness — основная ценность)
**Этап 3 — после стабилизации этапа 2** (оптимизация)
