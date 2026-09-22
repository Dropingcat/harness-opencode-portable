# Ревью: writing-контур (оркестратор-писатель, воркеры, связность проекта)

Дата: 2026-09-06. Тип: структурное ревью (контракты/связность), без изменения кода.
Метод: аудит агентов, shared-процессов, ссылок, live-раскладки, presence skills/субагентов.

---

## 1. Вердикт

Writing-контур — **функциональный каркас, но ЛОЖНЫЕ обещания и разъезд агент↔процесс**. 
Главная проблема не «нет контента», а **противоречие между `writing-orchestrator.md` (агент) и `shared/writing-orchestration-process.md` (процесс)**: они дают взаимоисключающие инструкции по диспатчу research.

---

## 2. Критические находки (блокеры)

### 🔴 К1. Агент диспатчит фантом-субагентов, процесс — нет
- `agents/writing-orchestrator.md` (Phase 4b): «dispatch three `task` calls: `researcher-gpt`, `researcher-glm`, `researcher-minimax`» + упоминает `synthesizing-researcher` (шаги 19, 23, 76, 96).
- Реальность: **ни одного из 4 файлов нет** в `agents/` (ни в HARNESS, ни в live). `researcher.md` — с `disable: true`.
- `shared/writing-orchestration-process.md` строка 55 честно фиксирует: «...those agent files do not exist (phantoms); the `researcher` agent is disabled. Use the built-in `general` sub-agent.» 
- **Следствие:** оркестратор, идущий по промпту агента, вызовет `task` с несуществующим типом → ошибка/пусто → зря потраченные итерации. И только потом заметит процесс. **Агент и процесс надо согласовать (Агент=истина для диспатча, процесс переписан правильно — выбери одно направление).**

### 🔴 К2. `ai-slop-avoidance` — обязательный skill, но ОТСУТСТВУЕТ
- `article-writer.md` требует загрузить его (шаги 1, 7, 29); `writing-orchestrator.md` — тоже (шаги 21, 118); `shared/article-writing-process.md` — требует (шаги 1, 8).
- На диске (и bundle, и live skills) **нет** ни `ai-slop-avoidance`, ни `deslop-ai-lint-skill` (из AGENT_SKILLS_RECONCILIATION как «замена»).
- **Следствие:** article-writer не может выполнить обязательный slop-audit перед handoff. Это детерминированный гейт, которого физически нет. Либо создать skill, либо снять требование в промпте.

### 🔴 К3. `research-process.md` — битая ссылка
- `article-writer.md` (шаг 30) и `researcher.md` (шаги 25, 28) ссылаются на `.opencode/shared/research-process.md` (правило RESEARCH_DIR), а также `shared/research-orchestration-process.md` упоминает `research-process.md`/`research-process.deprecated.md`.
- В `shared/` и по всему дереву такого файла **нет** (есть только `research-orchestration-process.md` — про верификацию, не про research-directory).
- **Следствие:** article-writer/researcher не могут разрешить `${RESEARCH_DIR}`, и правило записи статьи/отчёта мёртвое.

### 🔴 К4. `tvly` (Tavily CLI) не установлен
- `article-writer.md` (шаг 17, «Что у тебя есть» — `tvly`), `researcher.md` (все шаги) строят проверку фактов на `tvly`.
- `shutil.which('tvly')` → **NOT INSTALLED**. В live-окружении tool-имени `tvly` нет.
- **Следствие:** «verify missing facts with tvly» неисполнимо. Либо ставить Tavily (ключ), либо заменить на `webfetch`/`research_papers`/`search`.

---

## 3. Значимые (не блокеры)

### 🟡 B1. Агент↔процесс не синхронизированы по версиям
- `writing-orchestrator.md` построен на трёх model-specific ресечерах + handoff-паке; `writing-orchestration-process.md` уже принял решение «использовать general, одиночный вызов» и даже помечает модель-специфичных как phantoms. Это спру — надо либо переписать агента (убрать фантомы, перейти на general), либо восстановить файлы researchers. Учитывая, что процесс уже авторитетнее, рекомендую **переписать агента под процесс** (general sub-agent).

### 🟡 B2. Остаточные битые ссылки в shared
- `shared/orchestration-patterns.md` ссылается на `agents/security-auditor.md`, `agents/test-engineer.md` — **не существуют**. `shared/code-factory-process.md` ссылается на `W:\server2\shared\...` (архивный путь, не portable).
- Агенты пишут пути в стиле `.opencode/shared/...` (Claude-стиль) и `~/.config/opencode/...` — смешанные стили; рабочий в HARNESS — `${OPENCODE_HARNESS_ROOT}/shared/...`.

### 🟡 B3. reviewer/аудит для article-writer отсутствует
- В контуре писателя нет аналога `code-reviewer`/`code-auditor`: есть только article-writer и (сломанная) research-ветка. Из-за этого нет гейта «вторая пара глаз» перед публикацией (кроме slop-аудита, который отсутствует — К2).

### 🟡 B4. research-контур тоже недоделан (подтверждено из прошлой сессии)
- 13 Python-скриптов runner (numeric/post_processor/evidence/merge/cascade/circularity/content_verdict/factcheck_guard/justification/escalation + units/uncertainty/formulas) отсутствуют в HARNESS; `numeric_comparator.py` падает на импорте. Это отдельный проект (claimeai-service), но писатель при «research-backed» опирается на него же.

---

## 4. Связность проекта в целом (битые ссылки: итог аудита)

Аудит всех `.md`-ссылок в `agents/*.md` + `shared/*.md` (исключая переменные-шаблоны и переменные `${...}`):

| Потребитель | Битые ссылки (реальные) |
|---|---|
| `article-writer.md` | `research-process.md` (К3) |
| `researcher.md` | `research-process.md` (К3) |
| `writing-orchestrator.md` | `synthesizing-researcher.md`, `researcher-gpt/glm/minimax` (К1) |
| `research-orchestrator.md` | `SKILL.md` (generic), `final_report.md` (runtime-артефакт — норм) |
| `synthesizer.md` | `UNIFIED_ORCHESTRATION_PRINCIPLES.md` (есть) — ок |
| `shared/orchestration-patterns.md` | `agents/security-auditor.md`, `agents/test-engineer.md` (B2) |
| `shared/code-factory-process.md` | `W:\server2\...` (B2) |
| `experimenter.md`, `code-orchestrator.md` | `autoresearch.md` (файл-док отсутствует; есть skill `autoresearch`) — низкий приоритет |

**Живые плагируемые тезисы:** MCP_CAPSULE_ARCHITECTURE.md, UNIFIED_ORCHESTRATION_PRINCIPLES.md есть; research-orchestration-process.md есть; orchestration-thread-process.md теперь есть (новая капсула нити).

---

## 5. Что влияет на развитие (рекомендации, по приоритету)

1. **К1 — согласовать агент↔процесс писателя.** Решение: переписать `writing-orchestrator.md` под `general`-субагента (убрать фантом-диспатч), либо восстановить 4 файла researcher-агентов. Рекомендую первое (дешевле, один субагент + inline-синтез).
2. **К2 — решить судьбу slop-аудита.** Найти/создать `ai-slop-avoidance` skill (или заменить требование на конкретный чек-лист в процессе). Без него article-writer не имеет гейта.
3. **К3 — вернуть/создать `research-process.md`** с правилом `RESEARCH_DIR` (или выпилить ссылки из article-writer/researcher в пользу конкретных путей).
4. **К4 — заменить `tvly`** на `webfetch`+`research_papers`+`search` (или задокументировать обязательную установку Tavily).
5. **Согласовать пути**: единый `${OPENCODE_HARNESS_ROOT}/shared/...` вместо `.opencode/shared/...` и `~/...`.
6. **Добавить writer-ревьюер**: второй агент для ревью статьи (или гейт-чеклист) — вместо отсутствующего slop-аудита.

---

## 7. Резолюция (направление A выполнено, 2026-09-06)

Внедрено по всем найденным дырам:
- **К1** — `writing-orchestrator.md` переписан: research = built-in `general` (один task), фантом-диспатч убран (researcher-gpt/glm/minimax/synthesizing-researcher). Контракт выровнен с процессом.
- **К2** — создан skill `ai-slop-avoidance` (`skills/opencode-current/ai-slop-avoidance/SKILL.md`, детерминированный чек-лист A/B/C + правила исправления), скопирован в live skills. article-writer/writing-orchestrator теперь имеют реальный slop-гейт.
- **К3** — создан `shared/research-process.md` (правило RESEARCH_DIR = `${OPENCODE_HARNESS_ROOT}/research`, структура notes/reports/articles, реальные инструменты). Ссылки article-writer/researcher переведены на него.
- **К4** — `tvly` заменён на `webfetch`/`search` во всех промптах (article-writer, researcher, article-writing-process); tvly оставлен только как явно опциональный («only if `which tvly` succeeds»).
- **B3** — в writing-orchestrator Phase 5/6 добавлена самостоятельная проверка статьи (sources↔claims, vibe, no filler) + фолбэк на список из ai-slop-avoidance.
- **Пути** — `.opencode/shared/...` заменены на `${OPENCODE_HARNESS_ROOT}/shared/...`.
- **Баг sync** — `sync_to_live.py` писал агентов в `~/.config/opencode/agents/` (мн. число), а реальные живут в `agent/` (ед. ч.). Добавлен `dst_rel="agent"`; лишняя папка `agents/` удалена; все 15 агентов теперь = bundle (sha256).

Осталось из B/вторичного: `shared/orchestration-patterns.md` ссылается на отсутствующих `security-auditor.md`/`test-engineer.md`; `shared/code-factory-process.md` — на `W:\server2\...` (архив). Зафиксировать в трекере.