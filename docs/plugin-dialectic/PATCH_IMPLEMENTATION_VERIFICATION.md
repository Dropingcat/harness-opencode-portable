# Patch Implementation Verification — 2026-09-17

Метод: grep уникальных маркеров по `scripts/` (не по именам файлов).
Статус: `VERIFIED`.

## Итоговая таблица

| Патч (папка) | Маркеры | Внедрён? | Где |
|---|---|---|---|
| stage2 state_reducer (01) | `state_reducer` | ✅ PARTIAL→Coder | `scripts/code-factory/code_factory_runner.py` |
| stage3 artifact_provenance (01) | `artifact_provenance` | ✅ PARTIAL→Coder | `scripts/code-factory/provenance.py` |
| r4.1 tribunal composition (03) | TribunalCompositionPlan, AssessmentAssignment, AssessmentNeedRef | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_composition.py (17/5/45) |
| r4.2 evidence slicing (04) | EvidenceSlice, evidence_slice | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_evidence.py (25/39) |
| r4.3 independent role (05) | RoleExecutionKind, compile_role_instruction_pack, RoleVariantKind | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_role_runtime.py, tribunal_role_handbook.py |
| r4.4 L1 dialectic (06) | DialecticAction, `decide_dialectic_control` | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_dialectic.py (22/2) |
| r4.4 L2A argument graph (06) | ArgumentGraph, ArgumentRelationKind, build_argument_graph | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_argument_graph.py (53/17/6) |
| r4.4 L2B disclosure (06) | DisclosurePurpose, compile_dialectic_disclosure, QuestionPurpose | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_disclosure.py (15/7/14) |
| r4.4 L3A provider binding (06) | RoleProviderBinding, compile_question_provider_binding, ProviderBindingStatus | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_provider_binding.py (31/5/17) |
| r4.4 L3B grounding (07) | ResponseGroundingKind/Item, compile_execution_envelope | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_inquiry.py, tribunal_live_dialogue.py |
| r4.4 L3B live dialogue (07) | JobCtlLiveDialogueAdapter, execute_question, execute_answer | ✅ ИМПЛЕМЕНТИРОВАН | tribunal_live_dialogue.py |
| **writer v1 freeze** | CAUSAL_HYPOTHESIS, verification_dimensions, reference_fragment_set | ❌ **НЕ ВНЕДРЁН** | контракт-спецификация только |

## Выводы

1. **Весь R4-контур Researcher (r4.1 → r4.4 L3B) внедрён** и подтверждён маркерами.
2. **stage2/stage3** реализованы в Coder (code-factory), не в Researcher — это соответствует
   распределению (state reducer / artifact provenance — Coder-контур).
3. **writer v1 freeze — единственный НЕ внедрённый патч**: это контракт-спецификация
   (claim_type, verification_dimensions, reference_fragment_set и т.д.), код отсутствует.
   Связанные техдолги: TD-070 (claim_type enum), TD-071 (Q1A1..Q3A3 tribunal), TD-072 (DOM↔специалисты).

## Примечания к PARTIAL
- `slice_evidence` как функция отсутствует, но `EvidenceSlice` (25) + `evidence_slice` (39)
  подтверждают реализацию r4.2 — функция называется иначе.
- `DecideDialecticControl` (класс) отсутствует, но `decide_dialectic_control` (функция) +
  `DialecticAction` (22) подтверждают r4.4 L1.
- `grounding_profile` отсутствует, но `ResponseGroundingKind/Item/State` + `compile_execution_envelope`
  подтверждают r4.4 L3B.

## Дальше
- Writer v1 freeze: решить — внедрять контракты (TD-070/071/072) как отдельный этап, или
  переопределить схему в пользу текущего writer-core (extract/dom/uncertainty).