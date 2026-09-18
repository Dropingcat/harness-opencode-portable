# Capsule Coder DOM — Research & Data Artifact (2026-09-18)

Статус: `RESEARCH COMPLETE / PLAN READY / IMPLEMENTATION PENDING`
Цель: изолированная капсула Coder, где разработка фиксируется как DOM YAML-дерево
(функции + свойства + графы связей), для точечной мульти-разработки и потери ноль.

## 1. Research (GitHub/веб, 21 источник, подтверждено)

Ключевые выводы:
- **Готовых систем «каждая функция как YAML-граф для мульти-агентной разработки» НЕТ** — это ниша.
- **Аналоги по трём классам:**
  1. *Структура+правила*: Structurizr DSL (C4, model отдельно от views, CLI validate), ArchUnit (правила как unit-тесты), jQAssistant (граф+правила).
  2. *Граф вызовов*: **PyCG** (Apache-2.0, JSON adjacency list, ICSE'21) — первый выбор рёбер `CALLS`; pyan3 (AST), code2flow (orphaned), pydeps (импорты).
  3. *Stub-детекция*: vulture (unused+whitelist), dead (маркер `# dead: disable`), ruff (F401/F841), semgrep (паттерн-правило), radon (низкий CC/MI), ast-grep.
- **Git-гейт**: pre-commit framework — перегенерировать registry при коммите, fail при diff (schema drift).
- **Writer DOM (наш)** — эталон структуры: product+structure+graphs+uncertainty; graph_registry.yaml (G1-G12, node_types+edge_types+authority).

Источники: docs.structurizr.com/dsl, github.com/TNG/ArchUnit, github.com/jQAssistant, pypi PyCG, github.com/thebjorn/pydeps, github.com/scottrogowski/code2flow, pypi pyan3, github.com/jendrikseipp/vulture, github.com/asottile/dead, github.com/astral-sh/ruff, github.com/semgrep/semgrep, github.com/github/codeql, github.com/pre-commit/pre-commit, pypi radon, github.com/ast-grep/ast-grep, github.com/tree-sitter/tree-sitter, github.com/NiklasRosenstein/pydoc-markdown, templates/writer-dom-dissertation.yaml.
Полный JSON: `C:\Temp\opencode\research_code_dom.json`.

## 2. Локальные данные: заглушки в коде

**23 пустые функции в `scripts/researcher`** (не закоммичено в долг, не аннотировано):

| Файл | Функции | Природа |
|---|---|---|
| researcher_core/ports.py | now_ms, new, execute, __enter__, __exit__, put_state, append_event, enqueue_outbox, put_rejection, commit, rollback, rebuild_state, register, provider_for, capabilities, run, build, render (18) | **Protocol-интерфейсы** (намеренные абстракции, тела `...` — корректно) |
| researcher_core/capsules.py | run (1) | проверить: Protocol или конкретная заглушка |
| researcher_core/r0/ids.py | randrange, now_ms (2) | проверить: Protocol-подобные |
| researcher_core/tribunal_live_dialogue.py | invoke (1) | Transport-протокол |
| researcher_core/tribunal_role_runtime.py | execute (1) | **реальная заглушка** в @dataclass (не Protocol) |

Вывод: большинство — Protocol/ABC (норма, не долг). Требуется детектор, различающий:
- `Protocol`/`ABC`/`abstractmethod` → статус `interface` (ок);
- конкретная функция с пустым телом → статус `stub` (долг, требует issue/реализации).

Пример настоящей заглушки: `tribunal_role_runtime.py:46 execute(...) -> RoleWorkerDraft: ...` в @dataclass (не Protocol).

## 3. План: Capsule Coder DOM

### Схема (по образцу Writer DOM)

```yaml
# coder_dom.yaml (канон)
schema: coder-dom/1.0
product:
  id: "CDOM-001"
  kind: code
  status: drafted
  contours: [router, researcher, writer-core, code-factory, ...]
structure:
  contours:
    - id: researcher
      modules:
        - path: researcher_core/tribunal_live_dialogue.py
          functions:
            - id: "F-042"
              name: "execute_question"
              signature: "execute_question(parent_state_path, binding, envelope, transport, ...) -> (InquiryTurn, Receipt)"
              io: {inputs: [...], outputs: [...]}
              contour: researcher
              routing: "coder-worker:research-tribunal"
              status: done          # stub | drafted | done
              calls: ["compile_execution_envelope", "transport.invoke"]   # рёбра G-call
              called_by: ["Q1A1 loop"]
graphs:                       # реестр графов (как graph_registry.yaml)
  G-call:        {node_types: [function], edge_types: [CALLS]}
  G-import:      {node_types: [module], edge_types: [IMPORTS]}
  G-stub:        {node_types: [function], edge_types: [STUB, INTERFACE]}
  G-ownership:   {node_types: [function], edge_types: [OWNED_BY: agent/developer]}
uncertainty: {}               # аналог writer uncertainty для функций
```

### Компоненты

| Модуль | Назначение | Источник |
|---|---|---|
| `scripts/glossary/gen_api_index.py` (есть) | AST-реестр (signature/doc/decorators/line/contour/index) | наш |
| + рёбра CALLS | генератор графа вызовов | **PyCG** (опц.) / pyan3 / ast-рёбра сами |
| + stub-детекция | пустое тело vs Protocol | ast (наш) + radon CC + semgrep-правило |
| `scripts/glossary/coder_dom_build.py` | сборка coder_dom.yaml из gen_api_index + рёбра + stubs + owners | новый |
| `coder_dom.yaml` | канон (коммитится в git рядом с кодом) | артефакт |
| verify-гейт (pre-commit) | перегенерация → diff=0 (schema drift fail) | pre-commit framework |
| `G-ownership` контракт | routing: кто/какой агент развивает функцию | config/agent_gen.json (аналог) |

### Поток разработки (мульти-разработчики)

1. Разработчик берёт функцию-узел из `G-ownership` (не пересекаясь по строкам).
2. Меняет код → запускает `coder_dom_build` → `coder_dom.yaml` обновляется (signature/io/status/stub).
3. Коммитит код + DOM вместе (verify-гейт: registry согласован с AST).
4. Пустая функция: `status: stub` + issue-ссылка (или `# stub: <id>`) → видна в `G-stub` как долг.
5. Никто не теряет разработку: DOM — единственный источник правды о функциях.

### Открытые TD (из этого исследования)

| TD | Статус | Суть |
|---|---|---|
| **TD-076** | open | Coder DOM-аналог (этот план) |
| **TD-074** | open (M5-M6) | завершить синк/смоук glossary registry |
| **TD-077** | open | контракты reviewer/tester с evidence (галлюцинации) |
| **NEW-TD-078** | open | 23 stub/интерфейс-функции: разделить Protocol(норма) vs заглушки(долг); добавить в реестр стуба |