# Global Task Controller + Documentation Controller

Единый контроллер задач и документации для кодеров. Основан на `Z:\server\.hermes\kanban\global_kanban.py` (копия в `references/global-kanban/`) и на WP-структуре `workspace/агент кодер`.

## 1. Зачем два контроллера

- **Global Task Controller (global_kanban)** — оперативный: кто что делает сейчас, в какой фазе, с каким прогрессом. Один SQLite на всех агентов.
- **Documentation Controller (docs index + WP)** — структурный: что задокументировано, какие контракты утверждены, где техдолг, какие TRIZ-решения приняты.

Разделение ролей: task controller — результат (факт работы), doc controller — процесс/история (что решено и почему).

## 2. Global Kanban — схема

Копия: `references/global-kanban/global_kanban.py` (оригинал `Z:\server\.hermes\kanban\global_kanban.py`).

```sql
agents(id PK, name, group_name, created_at, last_seen)
statuses(id PK AUTOINCREMENT, agent_id FK, task_id, task_name, status, phase, progress, message, created_at)
index idx_statuses_agent(agent_id), idx_statuses_time(created_at DESC)
```

### API Python

```python
import sys
sys.path.insert(0, r'Z:\server\.hermes\kanban')
from global_kanban import GlobalKanban

gk = GlobalKanban()  # по умолчанию /home/orangepi/.hermes/kanban/global.db
# на Windows укажи свой путь:
gk = GlobalKanban(db_path=r'E:\Documents\Документы\doc_Opencode_agern\.kanban.db')

gk.register_agent("code-orchestrator", "Code Orchestrator", group_name="code-factory")
gk.report("code-factory", "WP-0", "Contracts", "WORKING", "2/8", "пишу models.py")
gk.report("code-factory", "TD-001", "tech_debt", "DONE", "1/1", "починил пути")
board = gk.get_board()  # последние статусы по агентам
```

### CLI

```bash
kanban-report code-factory "WP-0" WORKING "2/8" "пишу models.py"
kanban-board
```

### Статусы и фазы

- `status`: `PENDING|RUNNING|WORKING|PASSED|FAILED|BLOCKED|DONE` (в коде фабрики также `AMBIGUOUS` для эскалации).
- `phase`: `decompose|dispatch|review|test|tribunal|integrate|tech_debt|docs` — свободное поле, но используй единый словарь.
- `progress`: `1/8`, `3/5`, `45%` — человеко-читаемо, не парсится кодом.

### Где уже используется

- `agents/code-orchestrator.md` вызывает `GlobalKanban().report('code-factory', task_id, task_name, status, phase, progress, message)` на каждом переходе.
- `agents/triz-agent` (archived) использует `kanban.db` с FSM `QUEUE->GENERATOR->CRITIC->REWORK->DONE/FAILED` (см. `references/triz-agent/kanban/`).

## 3. Documentation Controller — реестр

Единый индекс документации — это сам `doc_Opencode_agern` + WP-документы.

| Слой | Файл | Назначение | Обновляет |
|---|---|---|---|
| Index | `MANIFEST.md` | инвентарь файлов + exclusion policy | code-orchestrator при каждом bundle pass |
| Contracts | `config/tool_skill_routes.json`, `config/guard_policy.json`, `config/tech_debt.json` | машиночитаемые контракты | code-orchestrator + profile_config |
| Principles | `CODER_DESIGN_PRINCIPLES.md` | ядро + архитектурные принципы + DoD | code-orchestrator |
| TRIZ | `TRIZ_FOR_CODERS.md` | паттерны triz-agent для кодеров | code-orchestrator при архитектурных задачах |
| TechDebt | `TECH_DEBT.md` | отдельный учет долгов | code-reviewer / code-orchestrator |
| Security | `SECURITY_GUARD.md` | guard как базовый способ защиты | auditor |
| Audit | `TOOL_SKILL_CONTRACT_AUDIT.md` | аудит tool↔skill↔contract | code-orchestrator |
| Tasks | `GLOBAL_TASK_CONTROLLER.md` (этот файл) | task + doc контроллеры | code-orchestrator |
| Source | `sources/SOURCE_MAP.md` | откуда что скопировано | code-orchestrator |
| WP Source | `references/agent-kirpichik/*` | WP-0..WP-4 фундамент | вручную при изменении workspace |

### WP-0..WP-4 как структурный трекер

Из `workspace/агент кодер/базовая документация/wp-*.md`:

- **WP-0 Фундамент и Контракты** — Pydantic модели, JSON Schemas, protocols, types, serialization. Без него нельзя начинать WP-1..WP-4. Блокирующий.
- **WP-1 Ядро оркестрации** — state machine, декомпозиция, dispatch.
- **WP-2 Исполнительный контур** — coder + verifier + sandbox.
- **WP-3 Процессный аудитор** — auditor отделен от критика, метрики, триггеры.
- **WP-4 Инфраструктура и безопасность** — sandbox (local/Docker), LLM gateway, бюджет, secret scan.

Каждый WP имеет `джун.md` (атомарные задачи 2-4ч) и `мид.md` (план интеграции). Это и есть трекер декомпозиции для кодеров.

## 4. Связка Task ↔ Docs

```
code-orchestrator --report--> GlobalKanban (status/phase/progress)
        |
        +--write--> MANIFEST / TECH_DEBT / tool_skill_routes (контракты)
        |
        +--read---> CODER_DESIGN_PRINCIPLES + TRIZ_FOR_CODERS (как проектировать)
        |
        +--guard--> SECURITY_GUARD (fail-closed)
```

Правило: любое изменение контракта (tool/skill/guard/tech_debt) одновременно:

1. меняет JSON/YAML в `config/`,
2. делает `gk.report(...)` с `task_id` контракта,
3. обновляет `MANIFEST.md` инвентарь.

## 5. Команды для Windows

```powershell
$root = "E:\Documents\Документы\doc_Opencode_agern"
$kanbanDb = "$root\.kanban.db"

# 1) проверить что global_kanban доступен
python -c "import sys; sys.path.insert(0, r'Z:\server\.hermes\kanban'); from global_kanban import GlobalKanban; gk=GlobalKanban(db_path=r'$kanbanDb'); gk.register_agent('code-orchestrator','Code Orchestrator','code-factory'); print('kanban ok', gk.db_path)"

# 2) отчет о фазе
python -c "import sys; sys.path.insert(0, r'Z:\server\.hermes\kanban'); from global_kanban import GlobalKanban; gk=GlobalKanban(db_path=r'$kanbanDb'); gk.report('code-factory','WP-0','Contracts','WORKING','decompose','2/8','пишу CODER_DESIGN_PRINCIPLES')"

# 3) посмотреть доску
python -c "import sys; sys.path.insert(0, r'Z:\server\.hermes\kanban'); from global_kanban import GlobalKanban; gk=GlobalKanban(db_path=r'$kanbanDb'); print(gk.get_board())"

# 4) проверить индекс документации
Get-ChildItem -LiteralPath $root -Recurse -File -Filter *.md | Measure-Object
Get-Content -LiteralPath "$root\MANIFEST.md" -TotalCount 40
```

На Pi путь по умолчанию `/home/orangepi/.hermes/kanban/global.db` — на Windows обязательно переопределяй `db_path`, иначе отчет уйдет не туда.

## 6. Миграция с triz-agent kanban

triz-agent использует локальный `kanban.db` с операциями `operations.py`/`storage.py`/`models.py`. Для кодеров:

- оставляем `references/triz-agent/kanban/` как пример FSM-оркестрации (QUEUE→GENERATOR→CRITIC→REWORK→DONE).
- для оперативных задач используем `global_kanban.py` — он уже агрегирует всех агентов (code-factory, triz-agent, research, etc.) в одном месте.

Не смешивай две БД: `kanban.db` triz-agent — для цикла концептов, `global.db`/`.kanban.db` — для оркестрации кодеров.

## 7. Динамические эвристики и NoAgents

- Эвристики решают, какую стратегию выбрать: см. DYNAMIC_HEURISTICS.md.
- NoAgents ветка — детерминированный путь без LLM: см. NO_AGENTS.md (stub mode, guard P0, schema).

## 8. Что делать дальше

- [ ] Создать `config/tech_debt.json` из таблицы в `TECH_DEBT.md`.
- [ ] Инициализировать `.kanban.db` в bundle и прогнать `gk.report` для текущих TD-001..TD-008.
- [ ] Подключить `GLOBAL_TASK_CONTROLLER.md` как обязательный индекс в `agents/code-orchestrator.md` (шаг "прочитай").
- [ ] Добавить `triz_required` ветку в `config/tool_skill_routes.json` для optimization/architecture задач.
```
