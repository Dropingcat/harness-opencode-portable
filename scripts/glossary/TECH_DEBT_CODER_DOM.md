# Coder DOM Capsule — Local Tech Debt

Дата: 2026-09-18. Локальный реестр долгов задачи (зеркало global config/tech_debt.json по записям, относящимся к Capsule Coder DOM).

## Активные

| ID | Severity | Суть | Привязка |
|---|---|---|---|
| TD-074 | medium | Glossary registry: M1-M4 done, M5-M6 (синк docs, smoke) не завершены | global |
| TD-076 | high | Coder DOM-аналог (этот план) | global |
| TD-077 | critical | Контракты reviewer/tester с evidence исполнения (галлюцинации; numeric_validator случай) | global |
| TD-078 | high | 23 пустые функции в researcher: Protocol vs заглушки; зафиксировать в реестре | global |
| L-TD-1 | high | Рёбра CALLS (граф вызовов) не генерируются (PyCG/pyan3 не подключены) | local |
| L-TD-2 | high | Stub-детекция не различает Protocol/ABC (interface) от конкретных пустышек (stub) | local |
| L-TD-3 | medium | `coder_dom.yaml` не строится (нет coder_dom_build.py) | local |
| L-TD-4 | medium | verify-гейт (schema drift) не реализован (нет pre-commit перегенерации) | local |
| L-TD-5 | medium | G-ownership контракт не определён (кто развивает функцию) | local |
| L-TD-6 | low | `coder_dom.yaml` не коммитится в git рядом с кодом (единица разработки) | local |

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