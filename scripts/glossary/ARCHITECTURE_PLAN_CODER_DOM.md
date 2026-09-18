# Coder DOM Capsule — Architecture & Development Plan

Дата: 2026-09-18
Статус: `DESIGN / IMPLEMENTATION PLAN`
Цель: изолированная капсула Coder, где разработка кода фиксируется как DOM YAML-дерево
(функции + свойства + графы связей), для точечной мульти-разработки и потери ноль.
База: `scripts/glossary/gen_api_index.py` (есть) + Writer DOM (эталон) + ресёрч (21 источник).

## 1. Архитектура

### 1.1. Схема `coder_dom.yaml` (по образцу Writer DOM)

```yaml
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
              status: done            # stub | interface | drafted | done
              stub_ref: null          # issue-ссылка если stub
              calls: ["compile_execution_envelope", "transport.invoke"]   # G-call
              called_by: ["Q1A1 loop"]                                     # обратные рёбра
              uses: ["config/tribunal_composition.yaml"]                    # G-import (данные)
graphs:
  G-call:      {node_types: [function], edge_types: [CALLS]}
  G-import:    {node_types: [module],   edge_types: [IMPORTS]}
  G-stub:      {node_types: [function], edge_types: [STUB, INTERFACE]}
  G-ownership: {node_types: [function], edge_types: [OWNED_BY: agent/developer]}
uncertainty: {}    # аналог writer uncertainty: функции с неопределённым io/статусом
```

### 1.2. Компоненты

| Компонент | Назначение | Статус |
|---|---|---|
| `gen_api_index.py` | AST-реестр public функций/классов | есть (A1) |
| + рёбра CALLS | граф вызовов | TODO (A4) |
| + stub-детекция | пустое тело vs Protocol | TODO (A5) |
| `coder_dom_build.py` | сборка coder_dom.yaml | TODO (A6) |
| `coder_dom.yaml` | канон (git) | TODO (B1-B3) |
| verify-гейт (pre-commit) | перегенерация → diff=0 | TODO (B4) |
| G-ownership контракт | routing: кто развивает | TODO (C1) |

### 1.3. Поток мульти-разработки

1. Разработчик берёт функцию-узел из G-ownership (не пересекаясь по строкам).
2. Меняет код → запускает `coder_dom_build` → `coder_dom.yaml` обновляется.
3. Коммит (код + DOM) — verify-гейт: registry согласован с AST.
4. Пустая функция: `status: stub` + issue → видна в G-stub как долг.
5. DOM — единственный источник правды; разработка не теряется.

## 2. Ветки разработки

### Ветка 1: Реестр (A) — фундамент
`A1-A3` (есть) → `A4` (рёбра CALLS) → `A5` (stub-детекция) → `A6` (coder_dom_build).
Приёмка: `function_index.json` + `coder_dom.yaml` собираются детерминированно.

### Ветка 2: DOM-капсула (B) — структура
`B1` (схема) → `B2` (графы) → `B3` (поля) → `B4` (verify-гейт).
Приёмка: coder_dom.yaml валиден по схеме; verify-гейт fail при schema drift.

### Ветка 3: Интеграция (C) — мульти-разработка
`C1` (ownership) → `C2` (адаптеры Writer/Researcher/Coder) → `C3` (кэш/провенанс) → `C4` (E2E).
Приёмка: два разработчика меняют разные функции без конфликта; прогресс сохраняется.

### Ветка 4: Долги (D) — качество
`D1` (TD-078 стубы) → `D2` (TD-077 контракты) → `D3` (G-stub реестр).

## 3. Сложности разработки

| Сложность | Оценка | Причина | Митигация |
|---|---|---|---|
| Рёбра CALLS (A4) | **высокая** | PyCG/pyan3 дают разную точность; высшие функции/декораторы/динамика | Сверка двух генераторов + ручная валидация на выборке; fallback на ast-рёбра |
| Stub-детекция (A5) | **средняя** | Protocol/ABC (тела `...`) — норма, не долг; конкретные пустышки — долг | Детектор: если класс наследует Protocol/ABC или метод abstractmethod → interface; иначе stub |
| Схема coder_dom (B1) | **средняя** | Зеркалит Writer DOM, но функции≠параграфы (связи/статусы другие) | Зафиксировать контракт coder-dom/1.0 + schema validation |
| verify-гейт (B4) | **средняя** | pre-commit перегенерация на большом дереве медленная; diff-стабильность | Инкрементальная перегенерация (только изменённые модули) + кэш |
| G-ownership (C1) | **низкая** | Просто поле routing в YAML | Контракт ownership в config |
| Адаптеры (C2) | **средняя** | Writer/Researcher/Coder разные контексты | Порты (из спеки semantic_field) — единый роутер, разные проекции |

## 4. Подводные камни интеграции

| Камень | Риск | Симптом | Решение |
|---|---|---|---|
| **Мусорные пути** | высокий | .venv/патчи/бэкапы попадают в реестр | gen_api_index уже исключает; расширить на новые (skills/server2-corpus) |
| **Нестабильный diff** | высокий | verify-гейт ложно падает (порядок, timestamps) | canonical JSON (sorted keys), stable order, исключить transient |
| **Кириллица/кодировки** | средний | cp1251 (TD-073) ломает вывод | PYTHONUTF8/reconfigure в скриптах |
| **PowerShell кавычки** | средний | SyntaxError в python -c (наблюдалось) | temp-скрипты, не inline -c |
| **Параллельная сессия пишет те же файлы** | высокий | tech_debt.json перезаписан (потеря TD-073/075) | git pull перед работой, merge-дисциплина |
| **Protocol vs stub путаница** | средний | ports.py (18) — интерфейсы, не долг; но tribunal_role_runtime.execute — stub | детектор классифицирует, реестр различает |
| **PyCG точность** | средний | рёбра CALLS могут быть неполными | сверка с pyan3, manual spot-check |
| **schema drift при расширении** | средний | версия coder-dom 1.0 → 1.1 ломает старые | schema_version + migration (как TD-065) |
| **Интеграция со спекой semantic_field** | высокая | 87-секционная спека — большой научный слой «на вырост» | не внедрять сейчас; только контракты-мосты (L-TD-6, TD-079) |

## 5. Приоритет и зависимость

```
A (реестр) → B (DOM) → C (интеграция) → D (долги)
E (semantic_field, спека) — отдельный трек «на вырост», после стабилизации A-C.
```

## 6. TD proposal (на вырост, из вложенной спеки)

- **TD-079 (proposal)**: вложенная спека HARNESS_SEMANTIC_RESEARCH_METHOD (87 секций) — оформить как глобальный TD для будущего научного слоя (InformationUnit, RTT, QuestionGraph, Hypothesis lifecycle, Evidence independence, ClaimReviewCase, Coder integration, fingerprints/event log).
- Признак: спека в архиве `docs/plugin-dialectic/HARNESS_SEMANTIC_RESEARCH_METHOD_IMPLEMENTATION_SPEC_V1 (1).md`; требует оформления в реестр и виртуальных E2E (как TD-048/049/050 направление).

## 7. Research findings по слабым местам (2026-09-18, 27 источников)

### S1. Рёбра CALLS
- **pyan3 — основной генератор** (функциональный уровень, `--text`/DOT, `--direction up` для callers; перерождён Feb 2026, Py3.10-3.14). PyCG — кросс-чек (JSON adjacency). tree-sitter — доп. проход для декораторов/async с меткой `syntax-only`.
- Формат: поле `confidence` у ребра (pyan3 TODO 1.0/0.0) — обязательное.
- FASTEN RCG — канонический формат call-graph (modules/namespaces/graph, версии 1-3), если понадобится пром-стандарт.
- Лимиты pyan3: lambdas, async-as-sync, результаты вызовов не разрешаются → рёбра для этих случаев — `syntax-only`.

### S2. Stub-детекция
- **Ни один инструмент не отличает interface от stub** (vulture/dead прямо помечают interface-функции как unused).
- Детектор самим: interface = `@abstractmethod`/ABC/Protocol в MRO (исключать); stub = `raise NotImplementedError` | docstring+pass+return None + маркер `# dead: disable` (стандарт dead).
- radon (cc/SLOC/MI) — сырьё; vulture `--min-confidence 100` — фильтр, НЕ решение.

### S3. Версионирование контракта
- Паттерн OpenAPI/AsyncAPI: обязательное поле `schema`-версии в документе; semver (additive=minor, breaking=major).
- **RFC 8785 JCS** (canonical JSON: сортировка ключей, IEEE754, UTF-8) — единый fingerprint для diff и миграционных карт 1.0→1.1.
- `generated_at` — в отдельное поле, исключаемое из хэша (паттерн FASTEN).

### S4. Verify-гейт
- pre-commit hook «перегенерировать → `git diff --exit-code` → fail при diff» (образец — официальные хуки vulture/dead).
- Стабильность diff: JCS-сортировка; CI-гейт `git status --porcelain`.

### S5. Ownership
- CODEOWNERS — только файлы (паттерны путей); генерировать из DOM как проекцию «файл → владелец».
- Dependency-aware: транспонированный call-graph (pyan3 `--direction up`) → при изменении сигнатуры тегировать владельцев callers-файлов.

### S6. Спека 87 секций
- Готового пакета нет. Кирпичи: **papermage** (слои OBSERVATION/MEASUREMENT/METHOD/ASSUMPTION как Entity + relations), **natasha/stanza** (RU/EN dependency для modality/negation, `advmod:Neg`), spaCy.
- RTT-валидатор и сама спека — собственная разработка.

## 8. Обновлённые решения (по ресёрчу)

| Слабое место | Решение (обновлено) |
|---|---|
| S1 CALLS | pyan3 основной + PyCG cross-check + tree-sitter (syntax-only) + поле confidence |
| S2 Stub | свой детектор: interface vs stub (маркеры), radon/vulture как сырьё |
| S3 Версии | schema-поле + semver + JCS fingerprint + миграционные карты |
| S4 Гейт | pre-commit «перегенерация → git diff --exit-code» + CI porcelain |
| S5 Ownership | CODEOWNERS из DOM (проекция) + transposed call-graph для dependency-aware |
| S6 Спека | papermage + natasha/stanza кирпичи; RTT — своё |