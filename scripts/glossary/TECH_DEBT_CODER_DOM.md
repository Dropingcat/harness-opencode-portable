# Coder DOM Capsule — Local Tech Debt

Дата: 2026-09-18. Локальный реестр долгов задачи (зеркало global config/tech_debt.json по записям, относящимся к Capsule Coder DOM).

## Активные

| ID | Severity | Суть | Привязка |
|---|---|---|---|
| TD-074 | medium | Glossary registry: M1-M4 done, M5-M6 (синк docs, smoke) не завершены | global |
| TD-076 | high | Coder DOM-аналог (этот план) | global |
| TD-077 | critical | Контракты reviewer/tester с evidence исполнения (галлюцинации; numeric_validator случай) | global |
| TD-078 | high | 23 пустые функции в researcher: Protocol vs заглушки; зафиксировать в реестре | global |
| L-TD-1 | high | Рёбра CALLS: **pyan3 основной** (функциональный, `--direction up` для callers) + PyCG cross-check + tree-sitter (декораторы/async, `syntax-only`) + поле confidence у ребра | local |
| L-TD-2 | high | Stub-детекция: свой детектор — interface (ABC/Protocol/abstractmethod в MRO) vs stub (`raise NotImplementedError`/docstring+pass+return None + `# dead: disable`); radon/vulture как сырьё | local |
| L-TD-3 | medium | `coder_dom.yaml` не строится (нет coder_dom_build.py) | local |
| L-TD-4 | medium | verify-гейт: pre-commit «перегенерация → git diff --exit-code → fail» (образец хуки vulture/dead); стабильность diff через RFC 8785 JCS | local |
| L-TD-5 | medium | G-ownership: CODEOWNERS как проекция из DOM «файл→владелец» + dependency-aware слой (transposed call-graph, тегировать callers при смене сигнатуры) | local |
| L-TD-6 | low | `coder_dom.yaml` не коммитится в git рядом с кодом (единица разработки) | local |
| L-TD-7 | medium | Версионирование контракта: обязательное schema-поле + semver (additive=minor, breaking=major) + JCS fingerprint + миграционные карты 1.0→1.1 | local |
| L-TD-8 | high | Спека 87 секций: кирпичи papermage (слои сущностей) + natasha/stanza (RU/EN modality/negation); RTT-валидатор — своя разработка (готовых нет) | local |
| L-TD-9 | medium | Coder DOM: шаблоны (аналог writer-dom-dissertation.yaml), контракт (schema+JSON Schema), скилл (напр. coder-dom.skill), привязка к роутеру (harness_run coder-route). Сейчас шаблон только для диссертации | local |

## Уточнение TD-078 (2026-09-18, подтверждено детектором)

Инвентаризация 23 «пустых» функций в researcher показала: **все 23 — интерфейсы** (Protocol/ABC,
тела `...`/pass — корректно). `tribunal_role_runtime.TribunalRoleWorker.execute` наследует Protocol.
**Реальных заглушек (pass/NotImplementedError вне интерфейсов) — 0.** TD-078 переформулирован:
не «23 заглушки = долг», а «детектор готов (interface vs stub), реальных stubs нет (0),
G-stub граф пуст; будущие заглушки должны помечаться `# stub:` маркером».

## Правило префиксов долгов (2026-09-18)

Разводим долги ПРЕФИКСОМ в общем `config/tech_debt.json` (не файлами), чтобы параллельные
сессии не конфликтовали:

| Префикс | Контур |
|---|---|
| `CD-*` | Coder / code-factory / glossary |
| `WR-*` | Writer |
| `RS-*` | Researcher |
| `PL-*` | OpenCode plugin / host |
| `TD-*` | общий/исторический (как было) |

Правила:
- Новая запись Coder-контура → `CD-NNN` (не TD-NNN).
- Номер = следующий свободный (max по префиксу + 1).
- Параллельная сессия другого контура не должна трогать CD-*.

Первые CD-долги:
- **CD-001**: полный пайплайн A1-A6 протестировать на portable (workspace OK).
- **CD-002**: шаблоны coder DOM (аналог writer-dom-dissertation.yaml), контракт coder-dom/1.0 (JSON Schema), скилл coder-dom, привязка к роутеру (harness_run coder-route). (= L-TD-9)

## Вложенная спека «на вырост» (из HARNESS_SEMANTIC_RESEARCH_METHOD_IMPLEMENTATION_SPEC_V1)

Полная спека (87 секций) — приложение к глобальному долгу как будущий научный слой.
Ключевые блоки для Coder/семантики, которые стоит учитывать при расширении капсулы:

- **InformationUnit/PropositionUnit** (секции 4): минимальные единицы извлечённой информации — аналог «клайма функции» в coder_dom.
- **Round-trip semantic validation** (20): scope/modality/causality/polarity drift — применимо к RTT функций.
- **TermConcept / false friends** (25): единая терминология — для именования функций/свойств.
- **Coder integration** (53): ComputationNeed/CodeWork contract, DerivationArtifact/DataArtifact/TestArtifact + provenance, WorkspaceRef обязателен.
- **Failure taxonomy** (64): RUNTIME_* vs EPISTEMIC_OPEN различаются — применимо к status функции.
- **Canonical JSON + fingerprints** (65): fp(x)=SHA256(canonical_json(x)) для версий артефактов.
- **Event log/provenance** (66): append-only события для каждой функции.
- **Storage** (67): canonical JSON + SQLite indexes (by_contour/by_module/by_status).
- **Порты/адаптеры** (81, из диалога): Writer/Researcher/Coder/Dialogue порты на одном роутере.

Полный текст спеки хранится в `docs/plugin-dialectic/HARNESS_SEMANTIC_RESEARCH_METHOD_IMPLEMENTATION_SPEC_V1 (1).md`
(архив) — для интеграции требуется оформить как отдельный глобальный TD (см. TD-079 proposal в плане).

## Правило
При регрессе локальные записи не переоткрываются без evidence. Перенос в global — через связку с глобальным ID.