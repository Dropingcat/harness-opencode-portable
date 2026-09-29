# МЕТА-ЦИКЛ HARNESS: ЕДИНЫЙ PYDANTIC-МОДУЛЬ (КОНСОЛИДИРОВАННЫЙ)

**Дата:** 2026-09-30
**Статус:** ФИНАЛЬНАЯ КОНСОЛИДАЦИЯ АРХИТЕКТУРЫ
**Назначение:** живой документ архитектуры — все сущности связаны перекрёстными ссылками, всё не попавшее в main → Legacy, всё доступно через семантический поиск.

---

## Область

Полный набор контрактов Meta-Cycle: V-1 Health Monitor, V1 State Ontology, V2 Evolutionary Controller, V3 Filter, V4 Experiment, V5 Prompt, V6 Negative Knowledge, V7 Execution, V8 Trace. Псевдокод — в `scripts/meta/` (реализация), этот документ — спецификация.

## Реализация в `scripts/meta/`

| Модуль | V-ветка | Статус | Файл |
|---|---|---|---|
| contracts.py | V2/V4 | ✅ реализован | DebtType, DebtSeverity, ThreatLevel, SectionDebt, AcademicParagraph, DraftSection, StateDelta, CatastrophicFailure |
| debt_cycle.py | V2 | ✅ реализован | DebtDrivenCycle, GateAdapter, ParagraphResolver |
| trace_store.py | V8 | ✅ реализован | TraceEntry, TransitionRecord, TraceStore, state_hash |
| health_monitor.py | V-1 | ✅ реализован | DriftSignal, HealthStatus, 5 каналов, ReanimationProtocol, HealthMonitor |
| state.py | V1 | 🟡 в разработке | StateVariable, ErrorVector, SystemState (StabilityLevel) |
| branch.py | V4 | 🟡 в разработке | SkillInvocation, Artifact, ExperimentRun, ExperimentBranch, BranchStatus |
| legacy.py | V6 | 🟡 в разработке | ExperiencePattern, LessonLearned, LegacyRecord, LegacyArchive |
| aar.py | V2/V6 | 🟡 в разработке | DeathCertificate, AfterActionReport |
| orchestrator.py | все | 🟡 в разработке | MetaCycleOrchestrator |

## Ключевые паттерны (инварианты)

1. **LLM = стохастический сопроцессор, Harness = детерминированный контроллер.** LLM не видит метрик/веток/состояний — только текстовую проекцию G(S_t).
2. **Immutable State:** каждое состояние S_t — неизменяемый снимок с SHA-256 hash.
3. **Debt-Driven Cycle:** Draft → Gates → Debt → Surgery → ReGate (≤3 итерации), иерархия угроз L0..L3.
4. **Death → AAR → Lesson → Pattern → Legacy:** каждая смерть учит систему; Legacy — активный фильтр, не кладбище.
5. **V-1 Health Monitor:** HP, жизни, достижения; право вето; реанимация при смерти.
6. **Полная трассируемость:** каждый вызов скила, каждый артефакт, каждый переход — в TraceStore.

## Схема связей

```
SystemState (V1) → StateDelta → CandidateState → ExperimentBranch (V4)
  ├── StateVariable[]                    ├── runs: ExperimentRun[] (SkillInvocation[])
  └── ErrorVector (Парето)               └── artifacts: Artifact[]
                                              │
                 успех → promote → SystemState'
                 провал → AfterActionReport → DeathCertificate → LegacyArchive
                                                              ├── ExperiencePattern[]
                                                              └── LessonLearned[]
TraceStore (V8) ← сквозная трассировка (entries, transitions, snapshots)
HealthMonitor (V-1) ← внешняя сила (HP, жизни, вето, реанимация)
```

## Открытые TD (обвязка)

См. REFACTOR_PLAN_2026-09-22.md §5b и config/tech_debt.json (V1-TD-*, NEW-*).