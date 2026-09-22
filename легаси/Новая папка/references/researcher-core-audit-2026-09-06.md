# Аудит: Researcher Core (E:\барахло\Documents\Default Project)

Дата: 2026-09-06. Тип: структурный + функциональный аудит, без изменения кода.
Метод: чтение модулей ядра (r0/r1/r3), прогон 360 тестов на изолированном venv,
CLI-прогоны (debt-scan, artifact-check), сверка связности с HARNESS research-контуром.

---

## 1. Вердикт

**Strong/A1.** Проект «код-первый» ресерчер — самый зрелый из всех WIP-контуров (research/writer).
- **360 тестов, все OK** (1.6s, изолированный venv + PyYAML).
- **debt-scan чистый**: всего 6 medium (магические числа в тестах r3_validators), 0 critical/high.
- Код дисциплинированный: frozen+slots dataclasses, ports-и протоколы, везде `debt-scan: ignore-line`
  для тех чисел, что являются доменными константами — техдолг явно управляется кодом.

---

## 2. Архитектура (что есть)

### Слои
- **R0 (детерминированное ядро)** — 14 модулей: entities, commands, events, enums, ids, graph,
  idempotency, projections, registry, serialization, sqlite_store, state_machines, transactions, validation.
  Event-sourcing с идемпотентностью, UnitOfWork, outbox, снапшотами, SQLite-адаптером.
- **R1 (граф знаний)** — Scope, Derivation, Assumption, Recommendation, Gap, Conflict, EdgeProposal —
  полноценные узлы исследовательской модели (не просто строки).
- **R3 (валидаторы)** — 769 строк детерминированной валидации: admission/structure/writer-gate,
  gap/conflict/risk builder'ы.
- **Периферия**: numeric (unit-конвертеры), uncertainty (± / диапазоны), formulas (Scherrer/Arrhenius),
  guard (vendored P0+P2 из doc_guard), capsules (loc-document-extraction, text-claim-extraction, local-corpus),
  offline_pipeline (smoke-конвейер), model_routing (policy-driven), budget (TokenMeter), artifact(+builder), debt, policy.
- **Ports**: ClockPort, IdFactoryPort, CommandHandlerPort, UnitOfWorkPort, EventProjectorPort,
  CapabilityRegistryPort, CapsuleRunnerPort, ArtifactBuilderPort — стабильные швы для SQLite/MCP/реального runtime.

### Инфраструктура качества
- 360 тестов, 15 НУМЕРОВАННЫХ доков (engineering-principles → migration-recovery-inventory).
- `config/research_policy.yaml` (14KB) — единственный источник лимитов/моделей/эвристик (в коде нет hardcode).
- CLI: `researcher-debt-scan`, `researcher-artifact-check` (зарегистрированы в pyproject).
- JSON-артефакты фабричных ревью (`worker_*.json`, `reviewer_*.json`, `tester_*.json`) — проект реально прогонялся через code-factory.

---

## 3. Находки

### 🔴 (не блокеры, но важные)

1. **Фикстура отстаёт от целевой схемы**: `malina_research_service_fixture.yaml` при
   `artifact-check` даёт **98 находок** (36 high: schema_version_gap + другие, 62 medium).
   Сигнал: feature-код опередил fixture/схему 0.2. Нужно обновить fixture (или понизить как «canonical pending»).

2. **`guard.py` хардкодит Windows-путь** `E:\Documents\Документы\doc_guard\src` как источник
   vendored-логики, с fallback на локальный минимальный набор при отсутствии. Работает, но:
   на другой машине без doc_guard и без этого пути подтянется **fallback-лист** (урезанный) —
   поведение guard изменится. Желательно: вынести путь в env/порт или заинлайнить версию.

3. **`runtime.py` содержит 2 почти-дубликата адаптеров** (MinimalArtifactBuilderAdapter /
   SqliteArtifactBuilderAdapter — идентичны). И `InMemoryEventProjectorAdapter` без аннотаций,
   но со ссылкой на неимпортированную `rebuild_state_from_events` (странная — вероятно недописано).
   Косметика, но указывает на неотполированный слой runtime-композиции.

### 🟡 (мелочи)

4. `__pycache__` с двумя версиями (cpython-311 и -312) в репо — .gitignore должен закрывать; если git-репо —
   проверить что .pyc не закоммичены.
5. В `r3_validators.py` кириллические паттерны выглядят мусорно из-за кодировки в выводе
   (re.compile с кириллицей) — возможно ок, но требует проверки в UTF-8.

---

## 4. Связность с HARNESS (взаимная)

### Что это значит для research-контура HARNESS
- HARNESS `scripts/research/numeric_comparator.py` **импортирует** `units`, `uncertainty`, `formulas`
  (top-level), которых в HARNESS **нет** (я ранее это зафиксировал как дыру, WS-16).
- **Здесь они есть**, но внутри пакета:
  - `researcher_core/uncertainty.py` → `parse_uncertainty`, `compare_with_uncertainty` (API совпадает!)
  - `researcher_core/formulas.py` → `detect_formula`, `check_constant` (API совпадает!)
  - `researcher_core/numeric.py` → `convert(value, from_unit, to_unit)`, `dimension(unit)` (совпадает с `units.convert/dimension`!)
  - **НО** `units.py` как отдельного модуля здесь нет — вместо него `numeric.py` (UnitRegistry).

**Вывод:** researcher-core является **эволюцией/портом** того же контура, что HARNESS-runner.
Для восстановления HARNESS research-контура можно АДАПТИРОВАННО взять эти модули:
скопировать `uncertainty.py`, `formulas.py` как есть, и make `units.py`-обёртку над `numeric.py`
(или добавить top-level `units.py`, экспортирующий `convert/dimension`). Это дешевле, чем ждать диск W.

### Обратная связь (project → harness)
- В проекте реализован guard (P0+P2) — это источник, к которому HARNESS guard должен стремиться.
- model_routing / budget / policy — тот же принцип «код решает», что у нас в фабрике.

---

## 5. Степень готовности по слоям

| Слой | Статус |
|---|---|
| R0 ядро (event-sourcing, sqlite, идемпотентность) | ✅ реализован, покрыт тестами |
| R1 entities (граф знаний) | ✅ реализован, валидируется |
| R3 validators | ✅ реализован (769 LOC), тесты |
| numerics / uncertainty / formulas | ✅ реализован, deterministic |
| guard | ⚠️ с fallback-путей (Windows-hardcoded), но работает |
| offline_pipeline | ✅ smoke-путь |
| runtime-композиция | 🟡 дубли адаптеров, мелкие недочёты |
| MCP-интеграция / реальный LLM-цикл | ⏳ **не подключено** (порты есть, адаптеров MCP нет) |
| researcher-оркестратор (opencode) | каркас в HARNESS; исполнительный слой build'ится здесь |

---

## 6. Рекомендации (по приоритету)

1. **Использовать researcher-core как источник недостающих HARNESS-модулей** (uncertainty/formulas/numeric→units).
   Дёшево, закрывает WS-16 research-часть без диска W. (Сделать как отдельную задачу с ревью.)
2. **Обновить `malina_research_service_fixture.yaml`** до схемы 0.2 (или пометить fixture как pending)
   — устранит 98 находок artifact-check и вернёт CLI в зелёное состояние.
3. **Вынести путь doc_guard из кода** guard.py в env/конфиг (порт).
4. **Причесать runtime.py**: убрать дубли адаптеров, задекларировать `rebuild_state_from_events`.
5. **Зафиксировать** в трекере проекта: промоция R2→R3 статусы, MCP-интеграция (порты готовы).
6. **Проверить .gitignore** против __pycache__ (минимум).

---

## 7. Резюме

Researcher-core — **здоровый, тестируемый, well-documented** проект с сильным детерминизмом.
Не «распиленная болванка», а полноценный движок verifier-слоя. Дырки — не в коде, а в
связывании: внутри проекта — фикстура/схема и runtime-полировка; наружу — интеграция с
HARNESS research-контуром (исполнительный слой) и MCP-адаптеры.

Приоритет: (1) синхронизация researcher-core ↔ HARNESS research-скриптов, (2) зелёный artifact-check.