# Развёртывание harness на новом сервере (относительные пути)

> **Контекст:** модуль harness-portable (Dropingcat/harness-opencode-portable, ветка `feature/b1-t2-core-config`) изначально разрабатывался на Windows-машине с абсолютными путями `E:\opencode_harness_portable\...`. Требование внешнего аудита **TD-AUD-2/3/6**: новый сервер НЕ должен зависеть от `E:\`, все пути — относительные к корню harness (`HARNESS_ROOT`) либо через переменную окружения.
>
> **Версия документа:** 2026-10-17. **Автор:** deployer (контракт 04/06 §4.14, 12).
> **Статус:** инструкция; применение на сервере — ручное (bootstrap вслепую НЕ запускать, см. §8.1).

---

## Оглавление

1. [Требования](#1-требования)
2. [Клонирование репозитория](#2-клонирование-репозитория)
3. [Относительные пути (ключевое)](#3-относительные-пути-ключевое)
4. [Установка окружения](#4-установка-окружения)
5. [Конфигурация OpenCode (`.opencode/opencode.json`)](#5-конфигурация-opencode-opencodeopencodejson)
6. [Синхронизация агентов (TD-DEV-60)](#6-синхронизация-агентов-td-dev-60)
7. [Проверка установки](#7-проверка-установки)
8. [Ограничения и известные проблемы](#8-ограничения-и-известные-проблемы)
9. [Проверка относительности после установки](#9-проверка-относительности-после-установки)
10. [Чек-лист развёртывания](#10-чек-лист-развёртывания)

---

## 1. Требования

| Компонент | Версия/требование | Источник |
|-----------|-------------------|----------|
| Python | **3.11+** (используется `.venv`) | `requirements-*.txt`, код использует `typing`, `tomllib`, `match`-синтаксис |
| OpenCode | Desktop/CLI **~1.18.30–1.18.34** (SDK/plugin пинится на `@opencode-ai/plugin 1.18.16`, peer `>=1.18.0`) | TD-AUD-12, `packages/opencode-harness-plugin/package.json` |
| Node.js | **20+** (только для сборки/проверки плагина) | `packages/opencode-harness-plugin/package.json` (`"type": "module"`, `tsc`) |
| git | любая актуальная | — |
| ОС | Windows / Linux / macOS (различия в шаге 4) | — |

---

## 2. Клонирование репозитория

```bash
git clone <repo-url> harness
cd harness
git checkout feature/b1-t2-core-config   # рабочая ветка; на сервере переключаемся на неё явно
```

- `<repo-url>` — https-URL репозитория `Dropingcat/harness-opencode-portable` (токен — только через хранилище/credential helper, в URL и в файлы НЕ писать; при выкладывании логов маскировать `ghp_***`).
- После клонирования НИЧЕГО не коммитится и не переписывается, пока не выполнен шаг 3 (относительные пути).

> **Правило:** рабочий каталог сервера далее обозначается `HARNESS_ROOT`. Все команды выполняются из него.

---

## 3. Относительные пути (ключевое)

Новый сервер должен быть независим от `E:\opencode_harness_portable`. Два места, где живут абсолютные пути:

1. **`.opencode/opencode.json`** — mcp-команды и plugin-path (см. §5).
2. **Скрипты и конфиги** — упоминания `E:\opencode_harness_portable` / `E:/opencode_harness_portable` в `.py`, `.json`, `.md`, `.yaml` (см. TD-AUD-3).

### 3.1 Проверка и нормализация

Запустить сканер (детерминированный, отчёт без изменения файлов):

```bash
python scripts/tools/relocate_paths.py --check --root .
```

Ожидаемый результат на свежесклонированном дереве: **список файлов с вхождениями** (в сурс-репо их десятки — это исторические упоминания и примеры), либо `OK` (если репозиторий уже очищен). `exit 1` при наличии вхождений — это норма до применения.

### 3.2 Замена (только на сервере!)

```bash
python scripts/tools/relocate_paths.py --apply --root .
```

- Каждый изменённый файл получает бэкап `<файл>.relocate.bak` рядом.
- Вхождения `E:\opencode_harness_portable`/`E:/opencode_harness_portable` заменяются на `$HARNESS_ROOT`.
- **ВАЖНО:** `--apply` НЕ запускается в исходном (LIVE) дереве `E:\opencode_harness_portable` — только в клоне/на новом сервере.

### 3.3 Файлы, которые требует ручной правки (не покрыты сканером полностью)

`relocate_paths.py` заменяет строковые вхождения. Ручное внимание:

- `.opencode/opencode.json` — заменить пути mcp и plugin (подробно §5).
- Случаи, где путь собирается из констант/`os.environ` — проверить grep-ом:

```bash
grep -R "opencode_harness_portable" --include=*.py --include=*.json --include=*.yaml --include=*.md . | grep -v "relocate.bak"
```

После замены — повторный `--check --root .` должен дать `OK` (кроме осознанных исключений, например исторических записей в `PROBLEMS_REGISTER.md`/журналах, где упоминание пути — часть факта, не выполнения).

### 3.4 `.venv` и окружение

- `.venv/` **не коммитится** (в `.gitignore`), создаётся локально (шаг 4.1).
- Переменная окружения `HARNESS_ROOT` должна указывать на корень: в Windows `set HARNESS_ROOT=%CD%` (или в PowerShell `$env:HARNESS_ROOT=(Get-Location)`), в Linux/macOS `export HARNESS_ROOT="$(pwd)"`. Можно добавить в `.env` (gitignored) или profile.

---

## 4. Установка окружения

### 4.1 Python venv

Windows:

```bat
cd %HARNESS_ROOT%
python -m venv .venv
.venv\Scripts\activate.bat
```

Linux/macOS:

```bash
cd "$HARNESS_ROOT"
python3 -m venv .venv
source .venv/bin/activate
```

### 4.2 Зависимости

В репозитории **нет единого `requirements.txt`** — требования разбиты по файлам:

| Файл | Назначение |
|------|------------|
| `requirements-core.txt` | Ядро: PyYAML, requests, sympy, matplotlib, numpy, **mcp>=1.0,<2.0** (SDK stdio-серверов), python-docx, markdownify, pypdfium2, openpyxl, PyMuPDF, tifffile, Pillow |
| `requirements-capability-bundle.txt` | Опциональный набор для исследовательских возможностей |
| `requirements-mcp-doc.txt` | Доп. зависимости MCP-серверов (если вынесены отдельно) |

Установка:

```bash
pip install -r requirements-core.txt
pip install -r requirements-capability-bundle.txt   # опционально
pip install -r requirements-mcp-doc.txt             # если есть
```

Минимальный набор по импортам кода (если пакеты выше отсутствуют в окружении): `openpyxl`, `numpy`, `pytest`, `PyYAML`, `requests`, `mcp`, `python-docx`, `markdownify`, `pypdfium2`, `PyMuPDF`, `tifffile`, `Pillow`, `sympy`, `matplotlib`.

> **TD:** единый `requirements.txt` — кандидат на создание (зафиксировать в PROBLEMS_REGISTER).

### 4.3 Plugin (Node/OpenCode Desktop)

Плагин уже собран: `packages/opencode-harness-plugin/dist-v2/v2/index.js` существует в репо — **отдельная сборка не обязательна**.

Если нужна пересборка/разработка:

```bash
cd packages/opencode-harness-plugin
npm install
npm run build        # вывод в dist/
```

Версия SDK/plugin — `@opencode-ai/plugin 1.18.16` (peer `>=1.18.0`); хост OpenCode ~1.18.30–1.18.34 совместим (TD-AUD-12).

---

## 5. Конфигурация OpenCode (`.opencode/opencode.json`)

**Файла `.opencode/opencode.json.example` в репо НЕТ** — шаблон ниже (это фактический конфиг LIVE с заменёнными путями).

Текущий (LIVE) конфиг содержит абсолютные пути; на сервере привести к виду:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "{{MODEL}}",                                  // модель — переменная/дефолт, НЕ хардкодить (TD-AUD-3)
  "small_model": "{{MODEL}}",
  "plugin": [
    "file:///{{HARNESS_ROOT}}/packages/opencode-harness-plugin/dist-v2/v2"
  ],
  "mcp": {
    "coder_router": {
      "type": "local",
      "command": [
        "{{HARNESS_ROOT}}/.venv/Scripts/python.exe",       // win; на linux/mac — .venv/bin/python
        "{{HARNESS_ROOT}}/mcp/coder_router_server.py"
      ],
      "enabled": true
    },
    "academic_search": {
      "type": "local",
      "command": [
        "{{HARNESS_ROOT}}/.venv/Scripts/python.exe",
        "{{HARNESS_ROOT}}/mcp/academic_search_server.py"
      ],
      "enabled": true
    },
    "doc_extract": {
      "type": "local",
      "command": [
        "{{HARNESS_ROOT}}/.venv/Scripts/python.exe",
        "{{HARNESS_ROOT}}/mcp/doc_extract_server.py"
      ],
      "enabled": true
    },
    "searxng_search": {
      "type": "local",
      "command": [
        "{{HARNESS_ROOT}}/.venv/Scripts/python.exe",
        "{{HARNESS_ROOT}}/mcp/searxng_search_server.py"
      ],
      "enabled": true
    }
  }
}
```

Правила:

- `{{HARNESS_ROOT}}` подставить фактическим абсолютным путём корня **сервера** (не `E:\...`).
- Если окружение требует `$`-переменные вместо подстановки — использовать `%HARNESS_ROOT%` (win) / `$HARNESS_ROOT` (unix) в командных путях (зависит от того, как OpenCode интерпретирует путь).
- **Secrets (API-ключи) — через env/`.env` (gitignored), НЕ в `opencode.json`** (TD-AUD-7). `.env` в репо отсутствует и не должен коммититься.
- `.env.example` (при наличии) — источник имён переменных.

---

## 6. Синхронизация агентов (TD-DEV-60)

После установки канон агентов нужно распространить в глобальные каталоги хоста (OpenCode читает их при старте):

```bash
python scripts/sync_to_live.py --apply --only agents
```

Ожидаемый результат — канонические md в `~/.config/opencode/agent` (и при необходимости `agents`).

Дополнительно (ручная зеркальная правка, т.к. `gen_runners` write пока сломан на LIVE, TD-DEV-58):

- скопировать 5 изменённых файлов `.opencode/agent/{code-tester,code-auditor,coder-worker,code-reviewer,glossary-maintainer}.md` в `.opencode/agents/` (plural), если хост использует этот каталог.

Проверка после синхронизации:

- в каноне `agents/*.md`: у 4 кодерских ролей (code-tester, code-auditor, coder-worker, code-reviewer) строка `hidden: false`; у glossary-maintainer строка `hidden` **отсутствует**;
- перезапустить OpenCode/Desktop-сессию;
- у code-orchestrator в `subagent_type` должны появиться 4 кодерские роли.

---

## 7. Проверка установки

```bash
# 1) health (если доступен плагин/CLI) — core_root должен = HARNESS_ROOT
python scripts/tools/check_health_canonical.py

# 2) реестр агентов в актуальном состоянии (без перезаписи)
python scripts/agent_gen/compile_agents.py --check
#    ожидается: {"ok": true, "agents": 26}

# 3) генераторы runner'ов:
python scripts/agent_gen/gen_runners.py --check
#    ВНИМАНИЕ: сейчас Exit 1 (TD-117: glossary-maintainer без primary-обёртки) — известное
#    ограничение TD-DEV-61; фиксируется как ожидаемое до решения владельца.

# 4) pytest новых P1-валидаторов
python -m pytest scripts/verify/test_xval_check.py scripts/code-factory/test_contract_validator_p1.py -q

# 5) плагин-харнесс (если CLI host):
#    harness_status --verbose → core_root = HARNESS_ROOT
```

---

## 8. Ограничения и известные проблемы

Полный список — `docs/BLOCKERS-2026-10-17.md` + `docs/PROBLEMS_REGISTER.md` (TD-DEV-58..61, TD-AUD-2/3/6/7/12). Ключевое при развёртывании:

| # | Проблема | TD | Влияние на новый сервер |
|---|----------|----|-------------------------|
| 8.1 | **Bootstrap перезаписывает config** (`scripts/meta/auto_bootstrap.py` при первом старте может переписать `.opencode/opencode.json`/`config/`) | TD-AUD-2 | **НЕ запускать bootstrap вслепую.** Конфиг править руками по §5; после поднятия окружения разобраться в инвариантах bootstrap и запускать с `--check`/dry-run. |
| 8.2 | `gen_runners.py` (write) падает: `TypeError: 'dict' object is not callable` (`reg.records()`, ~стр.210) | TD-DEV-58 | Досоздание primary-обёрток runner'ов недоступно до фикса; для glossary-maintainer — решение отдельное (TD-DEV-61). |
| 8.3 | Активация hidden-fix требует `sync_to_live` + рестарт OpenCode | TD-DEV-60 | Не активен сразу после клонирования; выполнять шаг 6. |
| 8.4 | Оффлайн-бандл не собирается/не поставляется | TD-AUD-6 | Новый сервер требует сеть для pip/npm, либо вендоренную копию `.venv`+`node_modules` под ту же платформу. |
| 8.5 | Secrets/host-токены | TD-AUD-7 | Только env/.env; в конфиг не писать. |
| 8.6 | Модель в `opencode.json` хардкожена у нас | TD-AUD-3 | На сервере оставить переменную/дефолт (см. §5). |

---

## 9. Проверка относительности после установки

```bash
python scripts/tools/relocate_paths.py --check --root .
```

- **Ожидаемо:** `OK` — вхождений `E:\opencode_harness_portable`/`E:/opencode_harness_portable` нет в `.opencode/`, `scripts/`, `config/` (кроме осознанных исторических упоминаний в документации/журналах).
- **Дополнительный grep:** `grep -R "E:\\\\opencode_harness_portable\|E:/opencode_harness_portable" .opencode scripts config` должен быть пустым.
- Проверить, что `opencode.json` не содержит `E:\` и ссылается на `.venv`/`mcp/`/`packages/...` относительно `HARNESS_ROOT`.

---

## 10. Чек-лист развёртывания

- [ ] Python 3.11+ доступен; OpenCode ~1.18.30–1.18.34 (TD-AUD-12)
- [ ] `git clone` + checkout `feature/b1-t2-core-config`
- [ ] `HARNESS_ROOT` задан (env)
- [ ] `relocate_paths.py --apply` выполнен (с бэкапами) либо дерево уже относительное
- [ ] `relocate_paths.py --check` → OK (без известных исключений)
- [ ] `python -m venv .venv` + активация
- [ ] `pip install -r requirements-core.txt` (+ capability, mcp-doc по необходимости)
- [ ] `.opencode/opencode.json` — пути через `HARNESS_ROOT`, secrets только env
- [ ] `dist-v2/v2/index.js` существует (плагин) или `npm install && npm run build` в packages
- [ ] `python scripts/sync_to_live.py --apply --only agents` + ручная копия в `.opencode/agents/`
- [ ] Перезапуск OpenCode; `subagent_type` содержит code-tester/code-auditor/coder-worker/code-reviewer
- [ ] `compile_agents.py --check` → ok (26)
- [ ] `pytest scripts/verify/test_xval_check.py scripts/code-factory/test_contract_validator_p1.py -q` → зелёный
- [ ] `gen_runners.py --check` → зафиксировать ожидаемый Exit 1 (TD-DEV-61)
- [ ] Отметить в PROBLEMS_REGISTER факт развёртывания + закрыть/обновить TD-DEV-58/60/61 по фактическому статусу