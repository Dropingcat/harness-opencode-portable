# Tribunal / Dialectic Tech Debt — Status README

Дата: 2026-09-17
Контур: Writer V1 freeze → Researcher Tribunal (Q1A1..Q3A3), специалисты, DOM-связка.

## Что УЖЕ сделано (реализовано и проверено)

| Компонент | Статус | Где |
|---|---|---|
| AssessmentAssignment (need → role_ids) | ✅ есть | `tribunal_composition.py:143` |
| need.level | ✅ есть | tribunal_composition |
| verify_claims (DOM→claims→researcher) | ✅ есть | `scripts/researcher/verify_claims.py` |
| Tribunal roles (handbook/composition/runtime) | ✅ есть | `tribunal_role_handbook.py` и др. |
| ArgumentGraph / dialectic / disclosure | ✅ есть | `tribunal_argument_graph.py`, `tribunal_dialectic.py`, `tribunal_disclosure.py` |
| Writer DOM-экстрактор (claims/objects) | ✅ работает | `writer-core` extract (v2 hybrid) |
| Writer plan/draftcheck/register/vectorsim | ✅ работает | `wc_cli.py` |
| Детерминированный Researcher-пайплайн | ✅ есть | `scripts/researcher/run_pipeline.py` |

## Что описано как контракт, но НЕ внедрено (freeze-пакет)

Freeze-пакет (`патчи/writer_v1_freeze_package/`) фиксирует целевую архитектуру,
но контракты **не реализованы в коде** (проверено 2026-09-17):

| Контракт (freeze) | В коде? |
|---|---|
| claim_type: SYNTHESIS/INTERPRETATION/COMPARISON/CAUSAL_HYPOTHESIS/EXTERNAL_FACT | ❌ claim_type='str', enum нет, CAUSAL_HYPOTHESIS=0 |
| verification_dimensions (VERIFIED/UNCHECKED/FAILED; SUPPORTED/.../OPEN; ESTABLISHED/.../UNKNOWN) | ❌ нет |
| reference_fragment_set / style_instruction / claim_evidence_selection | ❌ нет |
| research_dispatch_contract | ❌ нет (research_requests из uncertainty пуст — TD-069) |

## Техдолги трибунала/диалектики (открытые, high)

| ID | Проблема | Что нужно |
|---|---|---|
| TD-068 | Writer extractor не извлекает числовые/фактические claims | добавить числовые предикаты в extractor |
| TD-069 | uncertainty 'assumed' → research_requests=[] → долг не передаётся ресерчеру | маппинг 'assumed'→high/medium |
| TD-070 | claim_type не типизирован (нет enum, CAUSAL_HYPOTHESIS не внедрён) | enum ClaimType + классификация |
| TD-071 | Evidence-quality tribunal (Q1A1..Q3A3 поиск/классификация неопределённости) deferred | реализовать контур по уровням утверждений |
| TD-072 | DOM-блок утверждения не связан с тематическими ветвями трибунала (специалисты) | связать claim_type→thematic_branches→specialists |

## Схема целевого контура (из freeze + описания)

```
Утверждение (claim)
  └─ claim_type (SYNTHESIS | INTERPRETATION | COMPARISON | CAUSAL_HYPOTHESIS | EXTERNAL_FACT)
      ├─ уровни: гипотеза / верифицируемое (со ссылкой+цитатой) / диалектические конструкции
      └─ DOM-блок утверждения
          └─ thematic_branches (из трибунала + слоёв перед ним)
              └─ AssessmentAssignment: физика→физик, методология→методолог, ...
                  └─ верификация Q1A1→Q2A2→Q3A3 (поиск и классификация неопределённости)
```

## Дальше (рекомендуемый порядок)

1. **TD-068** (числовые claims) — фундамент: без них числа не верифицируются.
2. **TD-070** (enum ClaimType) — типизация уровней утверждений.
3. **TD-069** (uncertainty→research_requests) — починить передачу долга ресерчеру.
4. **TD-072** (DOM↔специалисты) — связать claim_type с трибуналом.
5. **TD-071** (Q1A1..Q3A3 контур) — финальный контур верификации по уровням.

## Честные границы

- Freeze-пакет = **спецификация контракта**, не реализация. Его нельзя считать «внедрённым».
- Патч `WRITER-V1-FREEZE-001.patch` **не применим** к текущему дереву (`git apply --check` → конфликты
  в IMPLEMENTATION_TRACKER/agents/config); при внедрении нужен перенос контрактов, а не `git am`.
- Уровни утверждений (гипотеза/верифицируемое/диалектические) — машиной пока не классифицируются.