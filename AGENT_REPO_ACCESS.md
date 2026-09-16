# Как агенту получить доступ к репозиторию из другой сессии

> Целевая аудитория: агенты Harness (code-orchestrator, coder-worker, research-orchestrator,
> writing-orchestrator, tribunal-judge и др.), запущенные в **новой сессии OpenCode**,
> которым нужно продолжить работу, начатую в предыдущей сессии, или взять репозиторий под работу.

---

## 1. Главный принцип: репо — это состояние, а не «память модели»

Модель не помнит предыдущую сессию. Всё, что тебе нужно, **лежит на диске**:
- сам репозиторий (рабочая директория);
- git-история (коммиты, ветки, теги);
- канбан-трекер (`.kanban.db` или каталог kanban);
- реестр памяти (`config/memory_registry.json`, `.runs/`);
- `project_context.py` — сводка «где мы»;
- архив handoff-пакетов (`handoff/`).

Никогда не полагайся на «я помню из прошлого раза» — **прочитай состояние** из этих источников.

---

## 2. Как найти, что уже есть

### 2.1 Найти корень harness
```bash
# Переменная должна быть задана bootstrap'ом (.env / setup_env).
echo "${OPENCODE_HARNESS_ROOT}"
```
Если пусто — вероятно, ты запущен вне окружения harness. Ищи корень по маркерам:
```bash
# Маркер: файл, который есть только в корне harness
ls "${OPENCODE_HARNESS_ROOT}/config/runtime_snapshot.json" "${OPENCODE_HARNESS_ROOT}/packages/opencode-harness-plugin/package.json" 2>/dev/null
```

### 2.2 Понять, в каком репозитории ты уже находишься
```bash
git rev-parse --is-inside-work-tree 2>/dev/null && git rev-parse --show-toplevel
```
- **Уже в репо** → переходи к разделу 3 (восстановить контекст).
- **Не в репо** → переходи к разделу 4 (взять репо в работу / создать принимающую директорию).

> Примечание: сам harness-модуль (`opencode_harness_portable`) — это тоже git-репозиторий
> (ветка `master`, тег `v1`). Рабочая задача может вестись **в другом** репозитории,
> подчинённом harness. Не путай «репо harness» и «репо задачи».

---

## 3. Восстановить контекст из существующего репозитория

### 3.1 Git-состояние
```bash
git status                                   # что изменено/не закоммичено
git log --oneline -15                        # последние коммиты (нить работы)
git branch -a                                # ветки (в т.ч. remote)
git stash list                               # отложенные изменения
```
Если видишь `DETACHED HEAD` или середину rebase/merge — сначала разберись с этим
(`git status` покажет; не начинай новую работу на полусобранном состоянии).

### 3.2 «Где мы» по трекеру
```bash
python "${OPENCODE_HARNESS_ROOT}/scripts/orchestration/project_context.py"
```
Вывод покажет: статусы канбана по контурам (code-factory/writing/research), открытые WS/TD,
остаток работы. Это твоя карта «что было начато и что осталось».

### 3.3 Канбан-история (по агентам)
```bash
python -c "import sys; sys.path.insert(0, '${OPENCODE_HARNESS_ROOT}/references/global-kanban'); from global_kanban import GlobalKanban; gk=GlobalKanban(db_path='${OPENCODE_HARNESS_ROOT}/.kanban.db'); print(gk.rows(limit=20))"
```
Либо — если канонический хелпер доступен:
```bash
python "${OPENCODE_HARNESS_ROOT}/scripts/orchestration/kanban_report.py" report <agent_id> <task_id> <status> <phase> <progress> <message>
```

### 3.4 Память (уроки прошлых сессий)
```bash
# Реестр уроков L3 — ищи по ключевым словам задачи
grep -i "ключевое_слово" "${OPENCODE_HARNESS_ROOT}/config/memory_registry.json" 2>/dev/null | head -20
```
Читай `memory` (mode=search) по ключевым словам, если инструмент доступен.

### 3.5 Handoff-пакеты (если были)
```bash
ls "${OPENCODE_HARNESS_ROOT}/handoff/" 2>/dev/null   # пакеты <проект>-<дата>
```
Handoff содержит: MANIFEST (что в поставке), CHANGES (что изменилось), TASKS (что дальше).
Это готовый «входной билет» для новой сессии.

### 3.6 Проверить целостность окружения
```bash
python "${OPENCODE_HARNESS_ROOT}/scripts/health_check.py"
# Ожидаем: Plugin Loaded / MCP Definitions / Guard Runner / DB Accessible — все OK.
```

---

## 4. Взять репозиторий в работу (репо нет / нужен новый)

### 4.1 Определить принимающую директорию
- Если путь задан в контракте/задаче — используй его.
- Если нет — создай рядом с harness: `${OPENCODE_HARNESS_ROOT}/../<имя-проекта>` или спроси
  пользователя через `question` (единственный легальный способ уточнения).

### 4.2 Оформить директорию как репозиторий по всем правилам
```bash
mkdir -p <принимающая-директория>
cd <принимающая-директория>
git init                                  # инициализация git-репо
```
Создай обязательную структуру:
- **`.gitignore`** — исключи `.venv/`, `__pycache__/`, `node_modules/`, `.runs/`, `*.db`, `.env`;
- **`README.md`** — назначение проекта, как запускать, контракты, ссылки на harness;
- **карта** — `MAP.md` (структура модулей/каталогов, кто за что отвечает);
- **трекер** — инициализируй канбан (глобальный `.kanban.db` через `kanban_report.py`/`GlobalKanban`,
  либо файл `TASKS.md`, если контур не подключён);
- **архитектурные файлы** — из `templates/` harness: `templates/adr-template.md` (ADR),
  `templates/component-spec-template.md` (спека модуля).

Затем **зафиксируй базовый срез** ДО первой правки кода:
```bash
git add -A
git commit -m "chore: bootstrap project scaffold (git, tracker, MAP, README, arch templates)"
```

### 4.3 Связать с harness (если нужно)
```bash
# Поставить OPENCODE_HARNESS_ROOT в окружение сессии (PowerShell):
#   $env:OPENCODE_HARNESS_ROOT = "E:\opencode_harness_portable"
# (bash):
#   export OPENCODE_HARNESS_ROOT="/path/to/opencode_harness_portable"
```

---

## 5. Что делать, если репозиторий «чужой» (уже существует)

### 5.1 Клонировать удалённый
```bash
git clone <url> <принимающая-директория>
cd <принимающая-директория>
git checkout <ветка>          # если нужна не дефолтная
```

### 5.2 Войти в существующий локальный репо
```bash
cd <путь-к-репо>
git status && git log --oneline -5
```

### 5.3 Убедиться, что ты не «утекаешь» в родительский git
Урок L3 из `memory_registry.json`: на Windows, если `OPENCODE_HARNESS_ROOT` — внутри
родительского репозитория, `git` может обнаружить **родительский** репо вместо целевого.
Проверь:
```bash
git rev-parse --show-toplevel   # должно указывать на целевой репо, НЕ на родительский
```
При необходимости используй `GIT_CEILING_DIRECTORIES` или работай в отдельной директории
вне родительского репо.

---

## 6. Быстрый чек-лист новой сессии

1. [ ] `echo ${OPENCODE_HARNESS_ROOT}` — корень на месте;
2. [ ] `git rev-parse --show-toplevel` — я в целевом репо;
3. [ ] `git status` / `git log --oneline -10` — понимаю состояние;
4. [ ] `python .../project_context.py` — знаю «где мы» по канбану;
5. [ ] `grep -i <задача> config/memory_registry.json` — учёл прошлые уроки;
6. [ ] `ls handoff/` — нет ли готового входного пакета;
7. [ ] `python .../health_check.py` — окружение здорово;
8. [ ] Если репо нет — создал принимающую директорию + git init + структуру + базовый коммит (раздел 4).

---

## 7. Запреты (fail-closed)

- **Не** начинай писать код вне git-репозитория.
- **Не** работай в середине rebase/merge/CHERRY-PICK, не разобравшись со статусом.
- **Не** полагайся на «я помню из прошлой сессии» — всегда читай состояние с диска.
- **Не** используй `git add -A && git commit` для чужих незакоммиченных изменений без проверки
  `git diff` (это не твои изменения — не подписывай их).
- **Не** путай репозиторий harness и репозиторий задачи.
- **Не** создавай принимающую директорию без разрешения, если контракт/задача не задают путь —
  используй `question`.