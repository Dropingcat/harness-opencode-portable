# -*- coding: utf-8 -*-
"""writer_core — детерминированный слой фабрики письма (M_WRITER_HARNESS).

Пакет упаковывает готовые и протестированные модули writer-гибрида
из одноразового каталога в переиспользуемый runtime-owned контрактный CLI +
фабрику письма по образцу фабрики кода:

    plan          — writing-orchestrator: структура будущего текста
                    (G1-дерево + G2-слоты + gaps) через structure_annotator;
                    plan --topic "<тема>" — каркас БЕЗ документа (секции
                    автореферата + слоты + gaps) до research;
    draftcheck    — article-writer: re-extraction черновика (детерминированно
                    через hybrid_extract) -> semantic RTT-дифф против
                    WriterContract -> constrained repair (дефект -> claim_id ->
                    span);
    live-cycle    — весь «живой» контур кодекра: bundle->claims->contract->
                    draft re-extraction->RTT-diff->(repair) (live_cycle.py);
    extract       — hybrid_extract_document -> artifact.json;
    graphs        — graph_builder_hybrid (G1-G16) -> graphs + sqlite;
    annotate      — structure_annotator.annotate_document -> structure_plan.json;
    consolidate   — консолидация версий (v1..v12) -> evolution_report;
    vectorsim     — cosine + dynamic_metrics (graph_vector).

Контракты фабрики письма (contracts.py): ResearchBundleLA, WriterContract,
Defect, VersionedArtifact. Цикл фабрики (factory_process.py):
draft -> reject/approve по RTT -> constrained repair (только дефектные
claim_id+span) -> иттерации ограничены. Полный контур поверх цикла —
live_cycle.py (research_bundle_from_path / writer_contract_from_path /
plan_from_topic / run_live_cycle / write_report).

Принципы:
- детерминированность: никаких LLM-вызовов в этом слое (polza — отдельный
  дешёвый guard/парсер, главный агент — opencode runtime);
- fail-closed: битый ввод -> JSON-ошибка + ненулевой exit code CLI;
- reuse: импортируются готовые модули, код не дублируется.
"""

__version__ = "0.1.0"
__all__ = ["cli", "contracts", "factory_process"]
