# Harness Developer README — как работать, не переписывая функционал

Дата: 2026-09-17. Цель: единая точка входа для дальнейшей разработки Harness
(Writer + Researcher + Coder + OpenCode plugin), без потери сделанного.

## Как пользоваться

1. **Что есть и как называется** → `GLOSSARY.md` (контур → функция → сигнатура → назначение).
2. **Что реализовано/внедрено/отложено** → `IMPLEMENTATION_STATUS.md`.
3. **Что чинить дальше** → `config/tech_debt.json` (открытые TD, priority: TD-066, TD-068..072).
4. **Техдолги трибунала** → `../plugin-dialectic/TRIBUNAL_TECH_DEBT_STATUS.md`.

## Контуры и как взаимодействовать

### Router
- `resolve(task_text, hints)` — маршрутизация. hints: `{"route_id": "...", "preferred_profile": "..."}`.
- Снапшот: `config/runtime_snapshot.json` (11 маршрутов). После правки — `scripts/router/compile_runtime.py --check`.
- ВАЖНО: `harness.run` требует непустой `task` (иначе BAD_REQUEST) — TD-066 (live peer mismatch).

### Researcher
- Трибунал: `TribunalCompositionPlan` → `AssessmentAssignment` → `EvidenceSlice` →
  `compile_role_instruction_pack` → `decide_dialectic_control` → `compile_execution_envelope` →
  `execute_question`/`execute_answer` (через транспорт).
- Верификация: `verify_claim(claim, source_text, policy)`.
- Детерминированный пайплайн: `run_pipeline(query, out_dir)` (search 3ch → relevance → extract → verdict).
- Тесты: `tests/researcher/` (593+2). Запуск: `python -m pytest tests/researcher -q` (PYTHONPATH=scripts/researcher).

### Writer (writer-core v2)
- CLI: `scripts/writer-core/wc_cli.py {plan|draftcheck|live-cycle|extract|graphs|annotate|consolidate|vectorsim|dom|review|uncertainty|register}`.
- Поток: `extract` (claims/objects) → `graphs` → `dom` (эталон DOM) → `uncertainty` (долг → research_requests).
- НЕДОДЕЛКИ: TD-068 (числовые claims), TD-069 (research_requests пуст при level='assumed').

### Coder / semantic transport
- `scripts/code-factory/semantic_transport.py`: `resolve_transport()`, `execute_coder_semantic(request)`,
  `build_coder_request(...)`.
- Bridge: `packages/opencode-harness-plugin/core/bridge_peer.py` (NDJSON full-duplex, harness-bridge-rpc/1.0).
- Fail-closed: пустой task → BAD_REQUEST; plugin без bridge → HOST_UNAVAILABLE.
- Тесты: `tests/coder/` (139).

### OpenCode plugin
- Entry: `.opencode/opencode.json` → `plugin: [file://.../dist/index.js]`.
- Tools: `harness_status`, `harness_run`. Reverse: `semantic.execute` (child session).
- Пересборка: `cd packages/opencode-harness-plugin && npx tsc -p tsconfig.json` (→ dist).
- После правки плагина — перезапуск OpenCode (конфиг кэшируется).

## Правила разработки (не ломать)

1. **Не переписывай реализованное** — развивай: меняй `compile*`/`resolve*` внутри, не вводя второй экземпляр.
2. **Единый semantic transport** (DEV-05): Coder/Writer/Researcher используют `SemanticExecutionRequest/Result`, не дублируй `opencode run`.
3. **Fail-closed**: пустой/невалидный вход → явная ошибка (BAD_REQUEST/HOST_UNAVAILABLE), не молчаливый fallback.
4. **Provider fallback** — только через новый preflight/RPB lineage (не silent switch).
5. **Core не зависит от OpenCode**: raw SDK-типы останавливаются в HostAdapter.
6. **Тесты перед коммитом**: researcher (pytest), coder (unittest), plugin (tsx --test + pytest).
7. **Патчи — НЕ применять `git am`**: writer_v1_freeze патч не применим к текущему дереву;
   переносить контракты вручную (см. TD-070/071/072).

## Порядок дальнейшей работы (рекомендуемый)

1. **TD-066** (live harness_run маршрут) — critical, блокирует live-калибровку.
2. **TD-068** (числовые claims) — фундамент верификации чисел.
3. **TD-070** (claim_type enum) — типизация уровней утверждений.
4. **TD-069** (uncertainty→research_requests) — починить передачу долга ресерчеру.
5. **TD-072** (DOM↔специалисты) → **TD-071** (Q1A1..Q3A3 контур) — финальный трибунал.
6. Writer v1 freeze контракты — внедрить после TD-070/071 (или переопределить схему).

## Реестр функций (автосбор, «по принципу Python-библиотек»)

Реестр генерируется детерминированно и пересобирается при добавлении функций:

```
# 1. Собрать JSON-индекс публичного API (контуры → модули → функции/классы + сигнатуры + docstring)
python scripts/glossary/gen_api_index.py --root <дерево> --out docs/glossary/function_index.json --label <label>

# 2. Рендер GLOSSARY.md из индекса
python scripts/glossary/render_glossary.py --index docs/glossary/function_index.json --out docs/glossary/GLOSSARY.md --label "<label>"

# 3. Дельта деревьев (что есть в полном, но НЕТ в portable → карта переноса v1.1)
python scripts/glossary/compare_trees.py --base <полный>/docs/glossary/function_index.json \
    --target <portable>/docs/glossary/function_index.json --out docs/glossary/PORTABLE_DELTA.md
```

- `function_index.json` — machine-readable индекс (для поиска/автодополнения).
- `GLOSSARY.md` — человекочитаемый рендер по контурам.
- `PORTABLE_DELTA.md` — дельта «полное дерево vs portable» (41 модуль + 93 функции отсутствуют в v1 → TD-D1).
- Правило: только публичные функции/классы (не `_private`) + задокументированные хелперы; тесты и мусорные директории исключаются автоматически.

## Как не потерять состояние

- `git log --oneline` — история коммитов (каждый шаг закоммичен).
- `docs/glossary/*` — этот комплект (обновлять при новых функциях; реестр пересобирать через `gen_api_index.py`).
- `config/tech_debt.json` + `config/development_tracker.json` — реестры.
- `docs/plugin-dialectic/evidence/*` — артефакты прогонов.
- Канбан: `scripts/orchestration/kanban_report.py report <agent> <task> <status> <phase> <n/N> <msg>`.