# Harness Implementation Status — что реализовано / внедрено / отложено

Дата: 2026-09-17. Источники: сверка патчей (`патчи/*`), ревью (`90_docs`),
freeze-пакет, авто-проверка маркеров по `scripts/`.

## Легенда

- **IMPLEMENTED** — код есть, маркеры подтверждены, тесты зелёные.
- **PARTIAL** — код есть, но частично / иное имя.
- **CONTRACT_ONLY** — описано в контракте/патче, кода нет.
- **DEFERRED** — явно отложено в документации.

## Карта по патчам

| Патч / контур | Статус | Ключевые файлы / функции | Проверено |
|---|---|---|---|
| stage2 state_reducer | IMPLEMENTED (Coder) | `scripts/code-factory/code_factory_runner.py` | ✅ |
| stage3 artifact_provenance | IMPLEMENTED (Coder) | `scripts/code-factory/provenance.py` | ✅ |
| r4.1 tribunal composition | IMPLEMENTED | `tribunal_composition.py` (TribunalCompositionPlan, AssessmentAssignment) | ✅ 17/5 |
| r4.2 evidence slicing | IMPLEMENTED | `tribunal_evidence.py` (EvidenceSlice) | ✅ 25 |
| r4.3 independent role | IMPLEMENTED | `tribunal_role_runtime.py`, `tribunal_role_handbook.py` (RoleExecutionKind) | ✅ 27 |
| r4.4 L1 dialectic | IMPLEMENTED | `tribunal_dialectic.py` (`decide_dialectic_control`, DialecticAction) | ✅ |
| r4.4 L2A argument graph | IMPLEMENTED | `tribunal_argument_graph.py` (ArgumentGraph, ArgumentRelationKind) | ✅ 53 |
| r4.4 L2B disclosure | IMPLEMENTED | `tribunal_disclosure.py` (DisclosurePurpose, QuestionPurpose) | ✅ 15 |
| r4.4 L3A provider binding | IMPLEMENTED | `tribunal_provider_binding.py` (RoleProviderBinding) | ✅ 31 |
| r4.4 L3B grounding | IMPLEMENTED | `tribunal_inquiry.py` (ResponseGroundingKind), `tribunal_live_dialogue.py` | ✅ |
| r4.4 L3B live dialogue | IMPLEMENTED | `tribunal_live_dialogue.py` (execute_question/answer, PluginBridgeProviderTransport) | ✅ |
| **writer v1 freeze** | **CONTRACT_ONLY** | `патчи/writer_v1_freeze_package/writer_v1_contracts.json` (claim_type, verification_dimensions, reference_fragment_set) | ❌ кода нет |
| evidence-quality tribunal (Q1A1..Q3A3) | DEFERRED | в freeze-патче помечен «Deferred to Researcher refactor» | ❌ |
| исследовательский детерм. пайплайн | IMPLEMENTED | `scripts/researcher/run_pipeline.py` | ✅ |
| Coder semantic transport (DEV-05 M1-M3b) | IMPLEMENTED | `scripts/code-factory/semantic_transport.py`, `packages/opencode-harness-plugin/core/bridge_peer.py` | ✅ 139 тестов |
| Writer DOM/plan/register/uncertainty | IMPLEMENTED | `scripts/writer-core/writer_core/cli.py` | ✅ |

## Открытые техдолги (блокируют развитие)

| ID | Статус | Суть |
|---|---|---|
| TD-068 | open/high | числовые claims не извлекаются extractor'ом |
| TD-069 | open/high | uncertainty 'assumed' → research_requests пуст (не передаётся ресерчеру) |
| TD-070 | open/high | claim_type не типизирован (нет enum, CAUSAL_HYPOTHESIS) |
| TD-071 | open/high | Q1A1..Q3A3 контур deferred |
| TD-072 | open/medium | DOM-блок не связан со специалистами трибунала |
| TD-066 | open/critical | harness_run live vs bridge_peer маршрут (peer mismatch) |

## Не путать в названиях

| Описание | Реальное имя в коде |
|---|---|
| диалектическое решение | `decide_dialectic_control` (функция), НЕ класс `DecideDialecticControl` |
| grounding | `ResponseGroundingKind` / `ResponseGroundingItem` (tribunal_inquiry), НЕ `grounding_profile` |
| slicing | `EvidenceSlice` + `compile_evidence_slice`, НЕ `slice_evidence` |
| назначение специалистов | `AssessmentAssignment` (need_ref → role_ids) |
| уровни утверждений (freeze) | `claim_type` (в коде str; enum НЕ реализован — TD-070) |