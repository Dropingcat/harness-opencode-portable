# ПОЛНЫЙ КОНТЕКСТ ДЛЯ КОДЕРА — Hermes Default-профиль (v2, неупрощённый)

## 1. ИСТОРИЯ ЗАПРОСОВ ПОЛЬЗОВАТЕЛЯ (сессия opencode 21.08, ses_fdaac3e37ffeX0LH6klld8h5bo)

1. «привет = хочу чтобы ты сделал ревизию /home/orangepi/Документы/ и /home/orangepi/Документы/doc_alisa_assistant/ /home/orangepi/.hermes/ обоих асистентов алисы и дефолтного подготовь отчёт»

2. «продолжмшь?»

3. «что можешь сказать по арзитектуре дефолтного профиля? в плане сдержек и противовесов — по большей степени мне хотелоь сделать ему больше автоматизации и упростить промты»

4. «распарсь sqlбазу сессии за сегодня — изучи что делали и дай глобально предложения по профилю»

5. «так же в профилде лежит документация в формате MD»

6. «дельные предложения — в беседе как ты мог увидеть — обсуждалась много ступенчатаатя роутер система где он входные ворота. а дальше дут по цепочки делегейте со своими mcp и вспомогательными скилами с четкими контрактами. сможем рассмотреть эту струкутуру подробно из с теми модулями которые можно прикрутить»

7. «сможешь — настроить обоих агентов? подключить скилы, плагины необходимые настроить оттестировать и хапустить. в идеале мне нужне для дефолта сервер для аналитика данных — по аналогии с perplexity там много чего понаделано уже из mpc браузеров и прочего. поисковая машина стоит sear но я так понимаю самое дельное это сделать mpc автоматику вызывающую opencod с плагином поиска и анализа — поиска по ряду источникво браузер, сервер поисковой, тематические сайты научные базы данных выгружал сырую инфу из них сопоставлял с задачей и давал отчёт. у тебя есть помоему разные полезные модули и мы в беседе их обсуждали»

8. «продооджай но не торопясь сервер внешний не успевает»

9. «проверь на гите какие есть подходящие модули для opencode для поиска и работы с сервисами так же я подключил mcp composio»

10. «продолжай»

11. «интеречные research-mcp точно нужно потестить. но ты прав — нуже слой умного роутера и для opencode или несоклько хардкод mcp котрые по разному запускают opencod — да какой толюфт давать внутри каждого но не сильный»

12. «предлагаю критически пробежаться по твоим предложенияи внести их в трекер задач и приступить к внедрению?»

---

## 2. ЧТО КОДЕР УЖЕ СДЕЛАЛ В СЕССИИ 21.08

- Прочитал конфиги: `/home/orangepi/.hermes/config.yaml`, `SOUL.md`, prisms, skills
- Прочитал alisa-assistant конфиги: `profile.yaml`, `SOUL.md`
- Прочитал `doc_alisa_assistant/` (00-README, 02-alisa-SOUL, 03-config, 07-TODO, 08-TODO, 09-master-plan-v2)
- Распарсил SQLite state.db Hermes за 21.08 — извлёк сообщения обоих профилей
- Нашёл: рабочая Алиса на AITunnel, документация и корневой конфиг на Ollama; открытые ключи; два gateway
- Создал 3 файла планов (УЖЕ СУЩЕСТВУЮТ, прочитай перед работой):
  - `/home/orangepi/Документы/doc_hermes_pi/coder-mcp-router-plan.md` — архитектура MCP coder-router
  - `/home/orangepi/Документы/doc_hermes_pi/coder-harness-plugins-plan.md` — каталог плагинов (поиск/парсинг/верификация/аналитика) с GitHub
  - `/home/orangepi/Документы/doc_hermes_pi/consolidated-proposals.md` — консолидированные предложения (10 направлений + приоритеты)
- Активировал oh-my-opencode-slim, сделал snapshot
- ПОПЫТАЛСЯ создать единый DOC-0 — застрял в цикле apply_patch (500+ ошибок)
- **НЕ ВНЕЁС реальных изменений** в конфиги/скрипты

---

## 3. ДИАГНОЗ DEFAULT-ПРОФИЛЯ (из анализа state.db за 21.08)

### Проблема 1: Слишком много глобального контекста
Default пытается одновременно помнить: Hermes, OpenCode, Composio, MCP, плагины, gateway, секреты, серверные проблемы, архитектурные идеи, старые отчёты, текущую установку.
За 21.08: **544M input tokens, 1729 API calls** — не нормальный режим.

### Проблема 2: Нет отдельного "постановщика задачи"
Default сам пытается быть: аналитиком, постановщиком, кодером, тестировщиком, админом, критиком — и ломается.

### Проблема 3: Нет жёсткого режима "одна мелкая задача — один контекст"
Вместо `цель → контракт → команда → проверка → запись результата`
получается `цель + старые обсуждения + плагины + OpenCode + gateway + ключи + спор о подходе`

---

## 4. ЦЕЛЕВАЯ 5-СЛОЙНАЯ АРХИТЕКТУРА (из сессии 21.08, НЕупрощённая)

```
Пользователь
   ↓
[Слой 0] Default Router / Intake — входные ворота
   ↓
[Слой 1] Task Classifier — классификация типа задачи
   ↓
[Слой 2] Context Filter / Scope Builder — резка лишнего контекста
   ↓
[Слой 3] Delegate Planner / Contract Builder — генерация ТЗ для делегата
   ↓
[Слой 4] Specialist Delegate Chain — один из 5 launchers:
   ├─ opencode_research_web      (веб-поиск, browser, DDG, Composio Search)
   ├─ opencode_research_academic (arXiv, OpenAlex, research-mcp, PapersFlow)
   ├─ opencode_service_task      (Composio: Calendar/Gmail/Drive/GitHub)
   ├─ opencode_code_worker       (кодинг, рефакторинг, tests)
   └─ opencode_profile_configurator (правка конфигов профилей)
   ↓
[Слой 5] Result Reconciler + Verification/Safety Gate
   ↓
Ответ пользователю + запись в память/трекер
```

### Слой 0: Default Router / Intake
Default-профиль = **тонкий диспетчер**, не комбайн.
Принимает запрос → классифицирует: `research / coding / system / calendar / kanban / docs / dangerous / unclear`

### Слой 1: Task Classifier
Превращает кривой человеческий запрос в нормальный task spec:
```json
{
  "task_type": "research|coding|calendar|system|docs|mixed",
  "goal": "...",
  "constraints": ["..."],
  "needed_sources": ["web", "local_docs", "scientific_db", "browser", "codebase"],
  "risk": "low|medium|high",
  "delegate_chain": ["..."],
  "success_criteria": ["..."]
}
```

### Слой 2: Context Filter
Решает: какой контекст нужен, какой вреден, что передавать делегату, что выкинуть.
Пример: если задача "поставь Composio" — НЕ передавать старые споры про архитектуру, длинные отчёты, историю ошибок. Передать: ОС, пути, текущий config, цель, критерии проверки.

### Слой 3: Delegate Contract Builder
Генерирует жёсткий контракт для подагента/кодера:
```yaml
role: coder
scope:
  read: ["/home/orangepi/.hermes/config.yaml", "/home/orangepi/.opencode/"]
  write: ["/tmp/composio-test/"]
forbidden: [expose_secrets, kill_processes, edit_global_config_without_approval]
success_criteria: [composio_cli_installed, version_command_works, auth_state_checked, report_written]
return_format: [summary, files_changed, commands_run, blockers, next_actions]
```

### Слой 4: 5 Hardcoded OpenCode Launchers (с малым люфтом)

#### 4.1. opencode_research_web — веб-поиск и первичный сбор
Разрешить: browser MCP, Composio Search, DDG wrapper, fetch/extract, read/write только в `/tmp/opencode/research-runs/<run_id>/`
Запретить: правки системных конфигов, фоновые процессы, sudo, установку пакетов
Люфт: менять поисковые запросы, 3-7 источников, повторить поиск если слабые
Выход: `{query, sources, raw_notes_path, summary, uncertainties}`

#### 4.2. opencode_research_academic — научные источники
Разрешить: opencode-research-papers, потом research-mcp, PapersFlow, OpenAlex/arXiv/Semantic Scholar
Запретить: широкий web search без причины, Sci-Hub без разрешения, запись вне research-run директории
Люфт: расширять запрос синонимами, citation graph depth 1-2, отбрасывать мусор
Выход: `{papers, citation_graph, evidence_table, gaps, recommended_next_searches}`

#### 4.3. opencode_service_task — Composio-сервисы (Calendar/Gmail/Drive/GitHub)
Разрешить: только Composio MCP, только явно указанные toolkits, dry-run по умолчанию
Запретить: массовые действия без подтверждения, удаление, отправка без preview
Люфт: искать нужный tool, подготовить payload
Выход: `{planned_action, toolkit, dry_run, requires_confirmation, payload_preview}`

#### 4.4. opencode_code_worker — кодинг
Разрешить: чтение repo, write только в project/worktree, tests/build, skills: verification-planning, simplify, worktrees
Запретить: править .hermes, .config/opencode, secrets; ставить системные пакеты; коммитить
Люфт: выбирать реализацию внутри контракта, нельзя менять цель, при росте scope — остановиться

#### 4.5. opencode_profile_configurator — настройка самих профилей
Разрешить: читать/править ТОЛЬКО:
  - `/home/orangepi/.hermes/config.yaml`
  - `/home/orangepi/.hermes/SOUL.md`
  - `/home/orangepi/.hermes/profiles/alisa-assistant/config.yaml`
  - `/home/orangepi/.hermes/profiles/alisa-assistant/SOUL.md`
  - `/home/orangepi/.config/opencode/opencode.jsonc`
Запретить: писать секреты в config, менять systemd без подтверждения, перезапускать gateway без подтверждения
Обязательно: backup перед изменением, валидация YAML/JSONC, smoke-test

### Слой 5: Result Reconciler + Verification/Safety Gate
Проверяет: command output, config path, service status, missing auth, verdict: partial/ok/failed
Critic подключается ТОЛЬКО когда: меняли конфиг, ставили MCP, работали с секретами, запускали кодера, была ошибка, задача multi-step.

---

## 5. МОДУЛИ ДЛЯ ПОДКЛЮЧЕНИЯ (из GitHub-исследования кодера)

### Уже доступны:
- **Composio MCP** — сервисный шлюз (Calendar, Gmail, Drive, GitHub, Slack, поиск)
- **opencode-research-papers** — arXiv, OpenAlex (уже в конфиге opencode)
- **oh-my-opencode-slim** — оркестраторская рамка (orchestrator/librarian/explorer/fixer)
- **browser MCP** — уже в Hermes config
- **DDG wrapper** — `~/.hermes/scripts/ddg-search.py`
- **Polza MCP** — уже в config

### Нужно поставить/протестировать:
- **opencode-mcp-tool-search** (`francisco-m001/opencode-mcp-tool-search`) — meta-tools: mcp_tool_search, mcp_tool_info, mcp_tool_call. Вместо загрузки всех tools — lazy search по контракту
- **research-mcp** (`chessy795/research-mcp`) — search_literature, walk_citations, read_paper, browser_download, OpenAlex/Semantic Scholar/CrossRef
- **opencode-papersflow** (`papersflow-ai/opencode-papersflow`) — Semantic Scholar, citation graph, related papers, graph expansion
- **perplexity-opencode** (`kevinmichaelchen/perplexity-opencode`) — Perplexity-like web search (нужен API key, этап 3)

### Плагины для research harness (из coder-harness-plugins-plan.md):
- **Поиск:** mcp-searxng, anysearch, tavily, exa, wigolo (keyless), free-web-search-ultimate (10+ движков без ключа), SearchForge, argus (RRF broker)
- **Парсинг:** mcp-docling (PDF/Office/HTML→MD), pullmd (URL→MD), pdf-parse, markdownify-mcp, webcrawl-mcp (trafilatura)
- **Верификация:** hlido-mcp (claim audit PASS/FAIL), touch-browser (confidence bands), entroly/WITNESS (анти-галлюцинация 0.844 AUROC), echology-io/decompose (authority/risk без LLM), data-aggregator-mcp (DOI-дедуп)
- **Аналитика:** networkx-mcp-server (community detection), cortex (knowledge graph), blackmount-nlp-mcp (NLP 18 яз. без LLM), data-profiler-mcp, ApeRAG (Graph RAG)

---

## 6. MCP TOOL REGISTRY (каталог для router'а)

```yaml
mcp_servers:
  browser:
    purpose: web automation
    owner: default
    risk: medium
  composio:
    purpose: external app automation (Calendar/Gmail/Drive/GitHub)
    owner: default/alisa
    risk: high
  polza-ai:
    purpose: external LLM endpoint
    owner: default
    risk: medium
  coder-router:
    purpose: coding delegation (opencode run --pure)
    owner: default
    risk: high
  alisa-kanban:
    purpose: tasks/reminders
    owner: alisa
    risk: low
  alisa-obsidian:
    purpose: notes/knowledge
    owner: alisa
    risk: low
```

## 7. SKILL REGISTRY (каталог для router'а)

```yaml
skills:
  composio-setup:
    trigger: composio, google calendar, app automation
    loads: [secret-safety, mcp-config, cli-install-check]
  opencode-delegation:
    trigger: coder, opencode, implement
    loads: [contract-builder, resource-guard, result-review]
  context-pruning:
    trigger: long session, confusion, repeated errors
  research-pipeline:
    trigger: research, search, find, analyse
    loads: [search-contract, source-verification, report-builder]
  profile-config:
    trigger: configure, setup, profile, SOUL
    loads: [backup-first, yaml-validate, smoke-test]
```

---

## 8. ТЕКУЩЕЕ СОСТОЯНИЕ

### Конфиг: `/home/orangepi/.hermes/config.yaml`
- Модель: deepseek-v4-flash:cloud (ollama-cloud), fallback → aitunnel
- Toolsets: hermes-cli, web
- MCP: polza-ai (remote), browser (local), coder-router (новый), composio (новый)
- Запуск через systemd hermes-gateway.service (без --profile), watchdog каждые 2 мин

### SOUL.md: `/home/orangepi/.hermes/SOUL.md` (уже упрощён до 39 строк в этапе 1)
- Роль: «Фёдор» — router и системный диспетчер
- Анти-сикофантизм, честность, git-запрет, делегирование через MCP

### Что уже сделано (этап 1, предыдущий запуск кодера):
- SOUL.md упрощён с 105 → 39 строк ✅
- coder_router_server.py создан (tool coder_run) ✅
- config.yaml обновлён: coder-router + composio подключены ✅
- Smoke-тесты пройдены ✅
- Бэкап: `/home/orangepi/.hermes/config.yaml.bak.20260822_060151_pre-coder-router`

### Инфраструктура:
- OpenCode 1.18.21, wrapper: `/home/orangepi/.opencode/bin/opencode` (VNNET прокси)
- Модель opencode: openai/gpt-5.5-fast (через прокси)
- Composio MCP: `https://connect.composio.dev/mcp`, заголовок `x-consumer-api-key`
- Google Calendar через Composio: подключён, felineenigmall@gmail.com
- Профили: alisa-assistant (НЕ ТРОГАТЬ), default (через systemd)

---

## 9. ПЛАН ВНЕДРЕНИЯ

### ЭТАП 1 —已完成 (неразрушающие изменения)
1.1. ✅ Упростить SOUL.md
1.2. ✅ Создать MCP coder-router
1.3. ✅ Подключить coder-router + composio в config.yaml
1.4. ✅ Smoke-тесты

### ЭТАП 2 — Многослойная router→delegate архитектура (ТЕКУЩИЙ)

2.1. Создать 5 hardcoded launchers (скрипты/контракты для opencode):
- `/home/orangepi/.hermes/mcp/launchers/opencode_research_web.py`
- `/home/orangepi/.hermes/mcp/launchers/opencode_research_academic.py`
- `/home/orangepi/.hermes/mcp/launchers/opencode_service_task.py`
- `/home/orangepi/.hermes/mcp/launchers/opencode_code_worker.py`
- `/home/orangepi/.hermes/mcp/launchers/opencode_profile_configurator.py`

Каждый launcher = MCP-сервер с одним tool, запускает `opencode run --pure` с:
- ограничением workdir
- ограничением разрешённых MCP/skills
- жёстким контрактом (allowed/forbidden/success_criteria)
- timeout
- запись артефактов в `/tmp/opencode/runs/<launcher>/<run_id>/`

2.2. Создать Task Classifier (prism или skill):
- `/home/orangepi/.hermes/prisms/intake.md` — правила классификации входящего запроса
- Определяет task_type, risk, delegate_chain

2.3. Создать Context Filter (prism):
- `/home/orangepi/.hermes/prisms/context_filter.md` — правила: что передавать делегату, что выкидывать
- Для мелких задач: ignore unrelated previous context

2.4. Создать Contract Builder (skill):
- `/home/orangepi/.hermes/skills/delegation-contracts/SKILL.md` — шаблоны контрактов для каждого launcher

2.5. Создать Verification Gate (prism):
- `/home/orangepi/.hermes/prisms/verify_gate.md` — проверка результата делегата

2.6. Создать Resource Guard (prism):
- `/home/orangepi/.hermes/prisms/resource_guard.md` — проверка CPU/RAM/processes перед запуском

2.7. Подключить MCP-плагины для research:
- Поставить mcp-searxng (локальный SearXNG)
- Поставить mcp-docling (PDF/Office→MD)
- Протестировать research-mcp (chessy795)
- Протестировать opencode-mcp-tool-search (francisco-m001)

### ЭТАП 3 — Оптимизация
3.1. Унификация провайдеров (provider_config.yaml)
3.2. Авто-верификация (WITNESS/hlido вместо ручных порогов)
3.3. Proxy в systemd units
3.4. PapersFlow (если research-mcp пройдёт тест)
3.5. perplexity-opencode (если Composio+DDG+Papers не хватает)

---

## 10. СТОП-УСЛОВИЯ

- ❌ НЕ ТРОГАТЬ alisa-assistant профиль (работающий, не ломать)
- ❌ Только `opencode run --pure` (не TUI)
- ❌ Бэкап конфига перед правкой
- ❌ Не коммитить в git
- ❌ Не убивать gateway процессы
- ❌ Не писать секреты в config (только env)
- ❌ Не запускать тяжёлые процессы без проверки CPU/RAM

---

## 11. ИСТОЧНИКИ (прочитай перед работой)

- `/home/orangepi/Документы/doc_hermes_pi/coder-mcp-router-plan.md` — архитектура coder-router
- `/home/orangepi/Документы/doc_hermes_pi/consolidated-proposals.md` — 10 направлений + приоритеты
- `/home/orangepi/Документы/doc_hermes_pi/coder-harness-plugins-plan.md` — каталог плагинов с GitHub
- `/home/orangepi/.hermes/SOUL.md` — текущий SOUL (уже упрощён)
- `/home/orangepi/.hermes/config.yaml` — текущий конфиг
- `/home/orangepi/.hermes/mcp/coder_router_server.py` — уже созданный MCP (этап 1)
- Сессия opencode `ses_fdaac3e37ffeX0LH6klld8h5bo` (21.08) — полные тексты ассистента выше