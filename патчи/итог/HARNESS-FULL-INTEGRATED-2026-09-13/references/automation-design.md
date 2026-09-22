# Automation Design: скиллы и автоматизация Hermes для resercher

**Тип:** анализ + проектирование + план (НЕ реализация).
**Дата:** 2026-08-19.
**Автор:** Research Engineer / Hermes-интегратор (анализ по локальным докам и скиллам Hermes, без web-поиска).
**Источники (проверены локально):**
- `~/.hermes/hermes-agent/AGENTS.md` (Skills, Plugins, Delegation, Curator, Cron, Kanban, Policies)
- `website/docs/user-guide/features/skills.md`, `plugins.md`, `cron.md`, `mcp.md`
- `website/docs/user-guide/messaging/webhooks.md`
- `hermes-already-has-routines.md`
- Существующие скиллы: `software-development/deep-testing-methodology` (+ `references/tag-graph-navigation.md`, `references/cor-matrix-dynamic-params.md`)
- Трекер `doc_hermes_pi/RESEARCHER_CLAIMS.md` (раздел «ГРАФ СВЯЗЕЙ ЗАДАЧ»), `resercher-todo.md`, `dresearch-compare-actuality.md`, `deadcode-roles-review.md`

---

## ЧАСТЬ A: Анализ возможностей Hermes для автоматизации

### A.1 Скиллы (`~/.hermes/skills/`)

- **Расположение и формат.** Каждый скилл — директория `<category>/<name>/SKILL.md` (+ опц. `references/`, `scripts/`, `templates/`, `examples/`, `assets/`). Передний YAML: `name`, `description` (<=60 симв.), `version`, `author`, `license`, `platforms`, `metadata.hermes.tags/category/related_skills/config`, `triggers`. Источник истины — `~/.hermes/skills/`; также поддерживаются внешние директории (`skills.external_dirs` в config.yaml).
- **Загрузка оркестратором (progressive disclosure).** Уровни: `skills_list()` -> `skill_view(name)` -> `skill_view(name, path)`. Скилл подтягивается только когда нужен; контент инжектится как **user message** (не system prompt) ради сохранения prompt cache.
- **Slash-команды.** Каждый установленный скилл = `/skill-name`. Можно стекать до 5 скиллов подряд. Бандлы (`~/.hermes/skill-bundles/<slug>.yaml`) группируют скиллы под одной командой (пример `research` = deep-testing-methodology + tag-navigation + cor-matrix).
- **Управление агентом.** Инструмент `skill_manage` (create/patch/edit/delete/write_file/remove_file) — процедурная память агента; записывает в `~/.hermes/skills/`. Curator (фоновая система) архивирует только скиллы с `created_by: "agent"` и не трогает pinned/bundled.
- **Конфиг скилла.** `metadata.hermes.config` -> `skills.config.<key>` в config.yaml, значения инжектятся при загрузке. `required_environment_variables` — секретные переменные с авто-промптом и passthrough в `terminal`/`execute_code`.
- **Условная активация.** `requires_toolsets` / `fallback_for_toolsets` / `requires_tools` / `fallback_for_tools` — скилл скрывается/показывается по наличию тулсетов.
- **Стандарт раздела SKILL.md (HARDLINE):** `When to Use`, `Prerequisites`, `How to Run`, `Quick Reference`, `Procedure`, `Pitfalls`, `Verification`; хелпер-скрипты — в `scripts/`, тесты — `tests/skills/test_<name>_skill.py` (stdlib + pytest + mock, без сети).

**Вывод для нас:** скиллы — основной механизм. Оба модуля (tag-navigation, cor-matrix) проектируются как скиллы с `scripts/` и `references/`.

### A.2 Плагины (`~/.hermes/plugins/`)

- Директория `~/.hermes/plugins/<name>/` c `plugin.yaml` + `__init__.py`, функция `register(ctx)`.
- Возможности `ctx.*`: `register_tool()` (новый инструмент LLM), `register_hook()` (жизненные хуки: `pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`, `on_session_start`, `on_session_end`, `subagent_stop`), `register_command()` (slash), `register_cli_command()` (`hermes <plugin> <sub>`), `inject_message()` (впрыск сообщения в сессию), `register_skill()` (скилл с неймспейсом `plugin:skill`), `dispatch_tool()`, `ctx.llm.complete()` (LLM-вызов).
- `pre_llm_call` может вернуть `{"context": "..."}` и вставить контекст в user message каждого хода — **это единственный механизм автовставки графа тегов в каждый промпт** без участия агента.
- Опт-in через `plugins.enabled` в config.yaml; project-local плагины (`./.hermes/plugins/`) требуют `HERMES_ENABLE_PROJECT_PLUGINS=true`.

**Вывод:** плагин НЕ нужен для v1. Он уместен только если потребуется hook `pre_llm_call` для принудительной автовставки графа в каждый ход (фаза 2+), когда скилл-процедуры недостаточно.

### A.3 Cron-задачи (`cronjob`)

- Инструмент `cronjob`: `create/list/update/pause/resume/run/remove`; управление через `/cron` или `hermes cron <verb>`.
- Расписания: `"30m"`, `"every 2h"`, 5-польный `"0 9 * * *"`, ISO one-shot.
- Поля джобы: `skills` (загрузка скиллов перед промптом), `script` (pre-run скрипт из `~/.hermes/scripts/`, stdout инжектится в промпт), `no_agent` (только скрипт, без LLM), `context_from` (чейнинг выходов), `workdir`, `deliver` (telegram/discord/local/...), `enabled_toolsets`, `model/provider` overrides.
- **Гейт `wakeAgent`:** скрипт может выдать `{"wakeAgent": false}` -> пропуск LLM-прогона за этот тик (дёшево для мониторинга). `[SILENT]` в финальном ответе -> подавление доставки (сработает только при проблеме).
- Сессия cron — изолированная, `skip_memory=True`, 3-минутный hard interrupt, не может создавать другие cron джобы.

**Вывод:** cron + `script` + `wakeAgent` — идеальный механизм для ежедневной проверки связности графа задач и регрессионной петли cor-matrix (алерт только при проблеме, LLM не тратится вхолостую).

### A.4 MCP-серверы

- `mcp_servers` в config.yaml: stdio (`command/args`) или HTTP (`url/headers`), авто-открытие тулзов с префиксом `mcp_<server>_<tool>`, per-server фильтрация (`tools.include/exclude`), каталог `hermes mcp catalog/install`.
- Уже подключён `polza-ai` (мониторинг баланса/моделей) — используется для LLM-стадий (factcheck, трибунал).

**Вывод:** MCP для наших модулей НЕ нужен — вся логика локальная (парсинг файлов, прогон пайплайнов скриптами). Внешний инструмент не требуется.

### A.5 Webhooks

- HTTP-сервер (порт 8644), маршруты в `platforms.webhook.extra.routes` или `hermes webhook subscribe`.
- Маршрут: `events`, `secret` (HMAC), `prompt` с `{dot.notation}` шаблоном, `filters`, `script`, `skills`, `deliver`, `deliver_only`.
- Событийные триггеры извне (GitHub PR, API-пуши, уведомления).

**Вывод:** для локального пайплайна webhook опционален (например, триггер перепрогона cor-matrix при появлении нового тестового материала). Низкий приоритет.

### A.6 delegate_task (субагенты)

- Изолированный контекст + терминал; `role="leaf"` (не может спавнить детей) / `role="orchestrator"` (может). Batch-режим: `tasks: [...]` параллельно (до 3 одновременно).
- `background=true` — возвращает id и результат приходит позже через очередь.
- Durability: background-delegation не переживает рестарт процесса — для выживающей работы использовать `cronjob`.

**Вывод:** batch `delegate_task` — механизм параллельного прогона двух систем (наш пайплайн + DResearch) в cor-matrix.

### A.6.1 ПАТТЕРН «агент-настройщик» (защита от переусложнения) — ВИДЕНИЕ 2026-08-21

**Проблема (выявлена в сессии):** оркестратор (default-профиль) перегружен контекстом — 30+ TODO, 20+ отчётов, планы, гипотезы. На простой задаче («подключи Composio MCP») эта нагрузка порождает ПЕРЕУСЛОЖНЕНИЕ: вместо «скопировать рабочий образец» — проектирование архитектуры, догадки, «исправления» того, что уже работает. Прямолинейный профиль (alisa-assistant) ту же задачу сделал тривиально — у него нет этого груза.

**Решение (структурное, не волевое):** для задач настройки/подключения использовать **агента-настройщика с изолированным чистым контекстом** — ровно паттерн subagent/delegate_task:

```
оркестратор: «подключи Composio»
   ↓ (задача уходит в чистый контекст subagent, БЕЗ моих TODO/отчётов/планов)
агент-настройщик (leaf, минимальный контекст — как у alisa-assistant):
   1. читает только релевантное: текущий конфиг + рабочий образец (как уже настроено у Алисы)
   2. формулирует промт кодеру: «копируй рабочий образец, НЕ проектируй»
   3. передаёт кодеру (opencode run)
   4. возвращает результат оркестратору
```

**Ключевое:** у агента **физически нет** перегруженного контекста оркестратора → переусложнение невозможно, потому что материала для него нет. Это НЕ волевое «постараться не усложнять» (подводит), а структурное ограничение контекста.

**Классификация задач:**
- ПРОСТЫЕ (настройка/подключение/чтение/установка) → агент-настройщик, чистый контекст, правило «копируй образец»
- СЛОЖНЫЕ (проектирование/исследование/архитектура) → оркестратор, полный контекст

**Реализация:** `delegate_task` (role=leaf) с минимальным context-полем (только задача + пути к конфигу/образцу), или отдельный скрипт/MCP, который собирает «чистый срез» (конфиг + образец Алисы) и отдаёт кодеру, минуя контекст оркестратора.

**Проверка после:** «я скопировал рабочий образец или изобрёл новое?» Если изобрёл на простой задаче — ошибка, откатить и взять образец.

### A.7 Прочее

- **Kanban** (SQLite board, `hermes kanban`): многопользовательская очередь задач, но это board-очередь, а не граф с рангами/связями — для контроля техдолга по графам не подходит как хранилище; подходит как опциональный интерфейс выполнения.
- **Curator**: жизненный цикл скиллов (архив неактивных agent-скиллов) — учитывать: пометить наши скиллы `pinned`, либо регулярно использовать.
- **Memory**: мелкие факты всегда в контексте; состояние графа лучше держать в файле-графе (JSON), а не в памяти (граф большой и мутируемый).

---

## ЧАСТЬ B: Дизайн скилла `tag-navigation` (контроль техдолга)

### B.1 Назначение

Менеджер воркфлоу по графам задач: каждый элемент техдолга (код или задача) = узел с тегами + ранг + связями; слои 0-3; порядок/зависимости; не терять активные задачи; алерт при застревании/потере связности. Интеграция с тегами в сообщениях оркестратора и трекером `RESEARCHER_CLAIMS.md`.

### B.2 Контракт графа (машиночитаемый)

Файл-граф: **`/home/orangepi/Документы/doc_hermes_pi/.tag-graph.json`** (в директории доков, чтобы жил рядом с источником истины; в `.gitignore` не нужен — это рабочий артефакт).

```json
{
  "schema_version": 1,
  "updated_at": "2026-08-19T12:00:00+03:00",
  "nodes": {
    "оркестрация-задач": {
      "tags": ["оркестрация-задач"],
      "rank": 0,
      "links": ["*"],
      "status": "active",
      "updated_at": "2026-08-19T12:00:00+03:00"
    },
    "задача1-починка": {
      "tags": ["задача1-починка"],
      "rank": 1,
      "links": ["тезис2-актуальность", "оркестрация-задач"],
      "status": "done",
      "updated_at": "2026-08-19T12:00:00+03:00"
    }
  }
}
```

Поля узла: `tags[]`, `rank` (0-3), `links[]` (имена узлов), `status` (active/blocked/done/todo), `updated_at` (для детекции застревания), `description`.

**Слои:** 0 = оркестрация (общий узел), 1 = активные задачи, 2 = связанные (данные/источники/зависимости), 3 = вторичные (todo/будущее). Ранг берётся из тегов-меток `[ранг: N]` и из таблицы трекера.

### B.3 Инварианты менеджера воркфлоу

1. Каждый узел ранга 1 имеет >=1 ссылку на узел ранга 2-3 и ссылку на узел 0.
2. Не существует узла ранга 1 со статусом `active` и пустыми ссылками (сирота).
3. Узел 0 существует и связан со всеми активными узлами (или отмечен `links: ["*"]`).
4. Ссылки указывают на существующие узлы (нет битых связей).
5. Нет дублей тегов (один тег = один узел).
6. Застревание: узел ранга 1 со статусом `active`, у которого `updated_at` старше порога (по умолчанию 2 суток) -> алерт.

### B.4 Порядок/зависимости

`report_graph.py` строит топологический порядок по `links` (что блокирует что), с приоритетом рангов: ранг 1 -> ранг 2 -> ранг 3. Выход — последовательность «сначала блокирующие/активные». Этот порядок оркестратор использует как «что делать дальше».

### B.5 Структура скилла

```
~/.hermes/skills/software-development/tag-navigation/
├── SKILL.md                    # инструкция оркестратору (When to Use, Procedure, Pitfalls, Verification)
├── references/
│   ├── graph-schema.md         # JSON-схема графа + правила слоёв/рангов (контракт)
│   └── workflow-rules.md       # инварианты, пороги застревания, правила алертов
├── scripts/
│   ├── parse_tags.py           # распознаёт [тег: имя] [ранг: N] [связи: ...] из строки
│   ├── build_graph.py          # sync: таблица RESEARCHER_CLAIMS.md + сообщения -> .tag-graph.json
│   ├── check_connectivity.py   # инварианты + застревание; вывод алертов; wakeAgent-выход
│   └── report_graph.py         # топологический порядок + статус (для оркестратора)
└── templates/
    └── alert-report.md         # шаблон алерта (потеря связности/застревание)
```

### B.6 Процедура использования (как оркестратор работает)

1. **На входе сообщения** (user или результат инструмента): если в тексте есть метки `[тег: ...]`, оркестратор вызывает `parse_tags.py`, извлекает узлы/ранги/связи и `build_graph.py` обновляет `.tag-graph.json`.
2. **Сверка с трекером:** перед выдачей тегов оркестратор сверяется с графом (по SKILL.md — «перед каждым сообщением с тегом сверяться с графом»); `build_graph.py` при каждом прогоне перечитывает таблицу «ГРАФ СВЯЗЕЙ ЗАДАЧ» в `RESEARCHER_CLAIMS.md` и смерживает.
3. **Выход оркестратора:** сообщения с тегами форматируются как `[тег: имя] [ранг: N] [связи: ...]` по текущему графу.
4. **Алерт:** `check_connectivity.py` проверяет инварианты; при нарушении выдаёт отчёт-алерт (по шаблону) в ответ и в ход рассуждения оркестратора (не может продолжать, пока не восстановлена связность) — правило «вернуться к графу».
5. **Порядок работы:** `report_graph.py` -> топологическая последовательность; активные (ранг 1) не теряются.

### B.7 Скрипт `parse_tags.py` (контракт входа/выхода)

- Вход: строка/текст; Выход: JSON-список `[{tag, rank, links[], source_pos}]`.
- Формат метки: `[тег: имя]` (обязателен), `[ранг: N]` (0-3, опционален — по умолчанию 3), `[связи: a, b, c]` (список имён, опционален).
- Детерминированный regex; устойчив к опечаткам/разнобою пробелов.

### B.8 Интеграция с cron (автоматический алерт)

Ежедневная проверка связности: `check_connectivity.py` копируется/оборачивается в `~/.hermes/scripts/tag-graph-check.py` (cron-скрипты живут только там) и используется как скрипт джобы с `wakeAgent`-гейтом:

```
hermes cron create "0 7 * * *" \
  "Граф задач проверен скриптом. Если он выдал алерт — сформулируй краткий статус техдолга и что делать дальше. Если чисто — [SILENT]." \
  --script tag-graph-check.py --skill tag-navigation --deliver telegram --name "tag-graph-check"
```

Скрипт сам решает: `{"wakeAgent": true, "context": {алерты}}` при проблеме, `{"wakeAgent": false}` при чистом графе — LLM и токены не тратятся на здоровое состояние.

### B.9 Проверка (Verification)

- `tests/skills/test_tag_navigation_skill.py`: парсер (правильные/битые метки), инварианты 1-6 (сирота, битая ссылка, дубль тега, застревание), порядок report_graph на фикстуре.
- Прогон на текущем графе из `RESEARCHER_CLAIMS.md` — должен построить `.tag-graph.json` без алертов (текущий граф согласован).
- Интеграционная проверка: сообщение с тегом оркестратора -> обновление графа -> алерт при разрыве.

---

## ЧАСТЬ C: Дизайн скилла `cor-matrix` (референс-анализ)

### C.1 Назначение

Локальный анализ методом референс: на вход — эталон(ы) (наш пайплайн + DResearch); прогон ОБЕИХ систем на одном тестовом материале; сбор **динамических параметров** (что каждая система реально нашла в процессе работы: объекты, дефекты, вердикты, caveats, remediation); построение **кор-матрицы** (объект x параметр x система); вывод сильных/слабых сторон и «что взять/сохранить»; регрессионная петля.

### C.2 Определение динамических параметров (точное, от пользователя)

«Переменные, создаваемые при подаче на вход функции тестовых данных. Могут быть уникальны для каждого проекта. Кор-матрица = сравнение того, что они нашли в процессе работы. Это и есть значения в этих динамических параметрах.»

Практически: при прогоне на тестовом материале система производит переменные (найденные объекты/дефекты/категории/verdicts/caveats/remediation). Динамический параметр = такая переменная конкретного прогона; кор-матрица = сопоставление этих переменных между системами на одном входе. Параметры **не фиксированы** — уникальны для проекта/прогона.

### C.3 Контракт кор-матрицы

Файл-прогона: **`/home/orangepi/Документы/doc_hermes_pi/.cor-matrix-runs/<дата>/matrix.json`** + отчёт `compare-report.md`.

```json
{
  "run_id": "2026-08-19",
  "input": "автореферат, раздел Актуальность",
  "systems": ["resercher", "dresearch"],
  "dynamic_params": {
    "объект/дефект": {
      "resercher": {"found": true, "detail": "caveat: источник дословно повторяет claim"},
      "dresearch": {"found": false, "detail": ""}
    }
  },
  "verdict_table": [ {"claim_id": "C5", "ours": "AMBIGUOUS", "tribunal": "OPEN", "dr": "VERIFIED", "match": "НЕТ"} ],
  "strong_ours": [], "strong_dr": [],
  "take_from_dr": ["remediation", "OUTDATED"], "keep_ours": ["caveats", "трибунал"]
}
```

### C.4 Структура скилла

```
~/.hermes/skills/research/cor-matrix/
├── SKILL.md                     # процедура: прогон -> сбор -> матрица -> вывод -> регрессия
├── references/
│   ├── methodology.md           # методология референса (объекты, не метрики; критерии сравнения)
│   └── dynamic-params-schema.md # схема динамических параметров + пример (Актуальность)
├── scripts/
│   ├── run_compare.py           # обёртка: один вход -> наш пайплайн + DResearch -> артефакты
│   ├── collect_dynamic.py       # парсинг артефактов (verdicts/processed/tribunal/judge_briefs/dresearch_factcheck) -> динамические параметры
│   ├── build_matrix.py          # объект x система -> кор-матрица (matrix.json + markdown-таблица)
│   └── regression_check.py      # diff двух прогонов «было -> стало»; алерт при регрессе по найденным объектам
└── templates/
    ├── compare-report.md        # шаблон отчёта (Методика / Таблица вердиктов / Найденные объекты / Сильные-слабые / Вывод)
    └── matrix-table.md          # markdown-вид кор-матрицы
```

### C.5 Процедура (Procedure)

1. **Вход:** эталон(ы) = наш пайплайн (`/home/orangepi/projects/claimeai-service/run_pipeline.sh`) + DResearch (`python3 -m engine factcheck snapshot_with_stance.json` в `/tmp/verify-dresearch/.../engine/`); тестовый материал (автореферат «Актуальность», exp1).
2. **Прогон обеих систем на одном входе.** Параллельно через batch `delegate_task` (2 задачи) или последовательно. Raw-артефакты каждого прогона сохраняются в `.cor-matrix-runs/<дата>/` (не перезаписываются) — это сырьё регрессии.
3. **Сбор динамических параметров** (`collect_dynamic.py`): из `verdicts.json`, `processed.json`, `tribunal.json`, `judge_briefs.json` (наш) и `dresearch_factcheck.json` (DResearch) извлекаются найденные объекты/дефекты, вердикты, категории, caveats, remediation, «что не проверено». Это и есть значения динамических параметров.
4. **Кор-матрица** (`build_matrix.py`): объект x система -> найдено/не найдено + detail; + таблица вердиктов (наш/tribunal/DResearch/совпадение).
5. **Вывод:** сильные/слабые стороны каждой, «что взять у референса, что сохранить» — по методологии из `RESEARCHER_CLAIMS.md` (объекты, а не метрики).
6. **Регрессионная петля** (`regression_check.py`): после каждого улучшения перепрогон; сравнение нового прогона с предыдущим; алерт при ухудшении по найденным объектам (что-то перестали находить).

### C.6 Интеграция с cron / по требованию

- По требованию: `/cor-matrix` (slash). Крон-версия (после изменений в пайплайне): джоба `cronjob(action="create", skill="cor-matrix", prompt="Перепрогнать референс-сравнение на фиксированном материале, сравнить с прошлым прогоном, при регрессе — отчёт.", schedule="every monday 9am", deliver="local")`.
- Регрессионный гейт `wakeAgent`: `regression_check.py` как `script` в `~/.hermes/scripts/` — запускается только если изменились исходники пайплайна (file-change gate) или материал.

---

## ЧАСТЬ D: Решения по автоматизации для Hermes

### D.1 Выбор механизмов (что и почему)

| Подзадача | Механизм Hermes | Обоснование |
|---|---|---|
| Скилл tag-navigation (процедура) | **Скилл** в `~/.hermes/skills/software-development/tag-navigation/` | Стандартный механизм процедурных инструкций; progressive disclosure; slash-команда; skill_manage для правок |
| Распознавание тегов в сообщениях | **Скилл + `scripts/parse_tags.py`** | Детерминированный парсер, вызывается оркестратором по инструкции SKILL.md |
| Обновление/синхронизация графа | **Скилл + `scripts/build_graph.py`** | md-таблица трекера -> graph.json; человек-источник и машина-источник |
| Алерт потери связности/застревания | **Cron + script (`wakeAgent`)** | Ежедневный тик; при чистом графе — без LLM (wakeAgent=false); при проблеме — отчёт в Telegram |
| Порядок/зависимости задач | **Скилл + `scripts/report_graph.py`** | Топологический порядок по связям |
| Скилл cor-matrix (процедура) | **Скилл** в `~/.hermes/skills/research/cor-matrix/` | То же, что выше |
| Параллельный прогон двух систем | **`delegate_task` (batch)** | Два изолированных субагента на одном входе |
| Регрессионная петля | **Cron + `script` (file-change gate)** + по требованию `/cor-matrix` | Перепрогон после изменений; сравнение «было->стало»; алерт регресса |
| Автовставка графа в каждый промпт | **Плагин `pre_llm_call`** (опционально, фаза 2) | Только если скилл-процедуры не хватает; добавляет сложность (opt-in, Python, рестарт) |
| Внешний инструмент | **MCP / webhook — не нужны в v1** | Всё локально; Polza уже есть как MCP для LLM-стадий; webhook опционален для внешних триггеров |

### D.2 Конкретные шаги реализации

**Фаза 1 — tag-navigation (первая):**

1. Создать `~/.hermes/skills/software-development/tag-navigation/` с `SKILL.md` по HARDLINE-структуре (When to Use / Prerequisites / How to Run / Quick Reference / Procedure / Pitfalls / Verification), frontmatter: `name`, `description` (<=60), `version`, `author`, `metadata.hermes.tags`, `related_skills: [deep-testing-methodology, cor-matrix]`.
2. `references/graph-schema.md` + `references/workflow-rules.md` (контракт + инварианты B.3).
3. `scripts/parse_tags.py`, `scripts/build_graph.py`, `scripts/check_connectivity.py`, `scripts/report_graph.py` (детерминированные, stdlib-only).
4. `templates/alert-report.md`.
5. `tests/skills/test_tag_navigation_skill.py` (stdlib + pytest + mock, без сети).
6. Прогнать на текущем графе из `RESEARCHER_CLAIMS.md` — построить `.tag-graph.json` без ложных алертов.
7. `~/.hermes/scripts/tag-graph-check.py` (тонкий cron-wrapper над `check_connectivity.py`) + `hermes cron create "0 7 * * *" ... --script tag-graph-check.py --skill tag-navigation --deliver telegram`.
8. Обновить `RESEARCHER_CLAIMS.md`: заметка «формализация и автоматизация теговой системы» -> статус «реализовано».

**Фаза 2 — cor-matrix (вторая):**

1. `~/.hermes/skills/research/cor-matrix/` с `SKILL.md`.
2. `references/methodology.md` + `references/dynamic-params-schema.md` (переиспользовать `cor-matrix-dynamic-params.md` из deep-testing-methodology).
3. `scripts/run_compare.py`, `collect_dynamic.py`, `build_matrix.py`, `regression_check.py`.
4. `templates/compare-report.md`, `matrix-table.md`.
5. Тесты `tests/skills/test_cor_matrix_skill.py`.
6. Первый прогон на материале «Актуальность» (уже есть артефакты в `/tmp/abstract_test/compare/`) — эталон кор-матрицы.
7. Cron-регрессия (file-change gate) или по требованию.

**Фаза 3 (опционально):** плагин с `pre_llm_call` для автовставки статуса графа в каждый ход; бандл `research` (deep-testing-methodology + tag-navigation + cor-matrix) в `~/.hermes/skill-bundles/research.yaml`.

### D.3 Оценка сложности и рисков

- **tag-navigation: сложность НИЗКАЯ-СРЕДНЯЯ.** Парсер меток прост. Риски: (а) два источника истины (md-таблица vs graph.json) расходятся — митигируется: `build_graph.py` синхронизирует в одну сторону (md -> graph), md остаётся для человека; (б) Curator может заархивировать скилл при неиспользовании — митигируется `pinned` или регулярным использованием; (в) cron-скрипты обязаны жить в `~/.hermes/scripts/` — тонкий wrapper, не дублирование логики.
- **cor-matrix: сложность СРЕДНЯЯ.** Риски: (а) нестабильность LLM-стадий (judge_brief/tribunal) -> различающиеся динамические параметры между прогонами — митигируется: сохранять raw-артефакты каждого прогона, сравнивать «было->стало» по найденным объектам, а не по exact-строкам; (б) дорогие прогоны (LLM) — регрессия по требованию + file-change gate, не ежедневная; (в) разная структура артефактов двух систем — единый слой `collect_dynamic.py`.
- **Плагин/MCP/webhook:** НЕ добавлять в v1 — снижает сложность и риски поверхностей расширения.

### D.4 Рекомендация: что реализовать первым

**Первым — `tag-navigation` (контроль техдолга).**

Причины:
1. **Немедленная польза:** оркестратор перестаёт терять активные задачи (ранг 1) и их связи — это была конкретная боль (см. `tag-graph-navigation.md`: «оркестратор терял, как ветки связаны»).
2. **Проще реализовать:** парсер меток + проверка связности + алерт — меньше зависимостей, быстрее деплой, легко проверить на текущем графе `RESEARCHER_CLAIMS.md`.
3. **Готовая база данных:** граф уже существует в трекере — синхронизация и первый прогон тривиальны.
4. **cor-matrix выигрывает от порядка:** регрессионная петля референса должна крутиться на управляемом техдолге (ясно, что и когда менялось), иначе «было->стало» зашумлено хаосом.

**Вторым — `cor-matrix`** как регрессионная петля над референсом: сначала порядок (tag-navigation), потом измерения (cor-matrix).

---

## ЧЕКПОИНТЫ

- [x] Анализ возможностей Hermes (скиллы/плагины/cron/MCP/webhook) — Часть A (по локальным докам, без выдумок)
- [x] Дизайн скилла tag-navigation (контроль техдолга) — Часть B
- [x] Дизайн скилла cor-matrix (референс-анализ) — Часть C
- [x] Решения по автоматизации (механизм, шаги) — Часть D
- [x] Рекомендация приоритета — D.4
- [x] Отчёт — этот файл

## ПРИЛОЖЕНИЕ: проверенные факты о Hermes (не выдумано)

- Скиллы: `~/.hermes/skills/`, progressive disclosure `skills_list/skill_view`, slash-команды, бандлы, `skill_manage`, Curator, `metadata.hermes.config`, HARDLINE-структура — подтверждено AGENTS.md и features/skills.md.
- Cron: `cronjob` tool, расписания, `skills`, `script` (только `~/.hermes/scripts/`), `no_agent`, `wakeAgent`, `[SILENT]`, `context_from`, delivery — подтверждено AGENTS.md и features/cron.md + реальные джобы в `~/.hermes/cron/jobs.json`.
- Плагины: `register(ctx)`, `ctx.register_tool/register_hook/register_command/register_cli_command/inject_message/register_skill`, `pre_llm_call` context inject, opt-in `plugins.enabled` — подтверждено AGENTS.md и features/plugins.md.
- MCP: `mcp_servers` stdio/HTTP, префикс `mcp_<server>_<tool>`, фильтры — подтверждено features/mcp.md; в конфиге уже есть `polza-ai`.
- Webhooks: порт 8644, маршруты, HMAC, `skills`, `deliver_only` — подтверждено messaging/webhooks.md.
- delegate_task: batch, roles, background, ограничения — подтверждено AGENTS.md.
- Существующие скиллы-прецеденты: `deep-testing-methodology` (SKILL.md + references/), в т.ч. `references/tag-graph-navigation.md` и `references/cor-matrix-dynamic-params.md` — подтверждено на диске.
