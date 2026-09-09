# Writer Core 2 — Semantic Document Build System

Версия архитектуры: **0.2 / paranoid production design**.

Writer Core 2 проектируется не как «AI-писатель», а как **типизированный компилятор сложных профессиональных документов**. Генеративная модель является лишь сменным исполнителем отдельных semantic operations. Истина, структура, данные, аргументация, артефакты, рецензирование, сборка и forensic-анализ существуют как разные bounded contexts.

## Миссия

Researcher отвечает: **что известно, при каких условиях и на каком evidence**.

Writer отвечает: **как преобразовать разрешённое знание в воспроизводимый документ, не усилив claims, не потеряв scope/uncertainty, сохранив вычисления, артефакты, provenance и историю решений**.

Build System отвечает: **что устарело, что требуется пересчитать/перепроверить и можно ли выпускать артефакт**.

Forensics отвечает: **какие признаки происхождения, стиля, процесса и lineage наблюдаются в работах**, не вмешиваясь в truth-state Writer/Researcher.

## Нормативная модель

```text
Requirements / policies
        ↓
Researcher epistemic projection (read-only)
        ↓
Writing Contract
        ↓
Writing Decomposition DAG
        ↓
Argument Graph + Discourse Graph + Artifact bindings
        ↓
Semantic Compiler / Realizer
        ↓
Document AST / Inline IR
        ↓
Round-trip semantic validation
        ↓
Dependency invalidation / selective rebuild
        ↓
Global consistency / review / release gates
        ↓
DOCX / PDF / MD build artifacts
```

Отдельно:

```text
Public/reference corpus → Forensics projections → calibrated hypotheses
```

## Порядок чтения агентом

1. `AGENTS.md`
2. `docs/01_INVARIANTS.md`
3. `docs/02_ARCHITECTURE.md`
4. `docs/03_ENTITY_AND_GRAPH_REGISTRY.md`
5. `graph_registry.yaml`
6. `docs/12_SEMANTIC_TYPE_SYSTEM.md`
7. `docs/13_WRITING_COMPILER_PIPELINE.md`
8. `docs/04_ROUTING.md` + `routing_table.yaml`
9. `docs/05_WRITING_CONTRACT.md`
10. `docs/07_TEMPLATE_SYSTEM.md` + `docs/15_TEMPLATE_EXECUTION_MODEL.md`
11. `docs/06_ROUND_TRIP_SEMANTIC_VALIDATION.md` + `docs/17_RTT_BENCHMARK_SPEC.md`
12. `docs/16_DEPENDENCY_INVALIDATION_BUILD_SYSTEM.md`
13. `docs/17_GLOBAL_CONSISTENCY_TERMINOLOGY.md`
14. `docs/18_QUANTITATIVE_UNCERTAINTY_ENGINE.md`
15. `docs/19_DATA_COMPUTATION_ARTIFACT_LINEAGE.md`
16. `docs/20_SECTION_INTERFACE_COMPRESSION_NOVELTY.md`
17. `docs/21_REVIEW_DECISION_CONFLICT.md`
18. `docs/22_RELEASE_EXPORT_VISUAL_QA.md`
19. `docs/23_BLOCKER_PROJECT_ORCHESTRATION.md`
20. `docs/24_CATASTROPHIC_SCENARIOS.md`
21. `docs/25_SECURITY_AUTHORITY_MUTABILITY.md`
22. `osint/*`
23. `docs/09_IMPLEMENTATION_MASTER_PLAN.md`
24. `docs/10_TEST_AND_ACCEPTANCE.md`
25. `docs/11_MIGRATION.md`

## Источники истины

- Git/YAML: schemas, policies, executable patterns, static registries.
- SQLite + append-only event log: runtime authoritative Writer state.
- Researcher Core: epistemic truth and evidence ownership.
- Data/computation store: immutable/raw and derived computational artifacts.
- Markdown/DOCX/PDF: reproducible build outputs, **не** truth store.
- `legacy_sources/`: только исторический контекст и migration evidence.

## Главные milestones

**M1**: надёжный one-paragraph semantic compiler.  
**M2**: dependency-aware section compiler.  
**M3**: quantitative/artifact reproducibility.  
**M4**: full-document consistency + review + release pipeline.  
**M5**: corpus learning and forensic analysis only after M1–M4 metrics are stable.
